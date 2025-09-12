#!/bin/bash

# Google News Scraper - Production Deployment Script
# Secure deployment script for production environment

set -e  # Exit on any error

echo "🚀 Google News Scraper - Production Deployment"
echo "=============================================="

# Configuration
PROJECT_NAME="google-news-scraper"
ENV_FILE=".env.production"
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
MAX_BACKUP_DAYS=7

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Security checks
security_check() {
    log "Performing security checks..."
    
    # Check for required secrets
    if [ ! -d "secrets" ]; then
        error "Secrets directory not found. Create secrets/ with required password files."
        exit 1
    fi
    
    if [ ! -f "secrets/postgres_password.txt" ]; then
        error "PostgreSQL password file not found: secrets/postgres_password.txt"
        exit 1
    fi
    
    if [ ! -f "secrets/redis_password.txt" ]; then
        error "Redis password file not found: secrets/redis_password.txt"
        exit 1
    fi
    
    # Check file permissions for secrets
    chmod 600 secrets/*.txt
    success "Secret files permissions secured"
    
    # Validate environment file
    if [ ! -f "$ENV_FILE" ]; then
        error "Production environment file not found: $ENV_FILE"
        exit 1
    fi
    
    # Check for required SSL certificates
    if [ ! -d "data/ssl" ]; then
        warning "SSL certificates directory not found. HTTPS will not be available."
        warning "Create data/ssl/ with cert.pem, key.pem, ca-cert.pem, and dhparam.pem"
    fi
    
    success "Security checks completed"
}

# Pre-deployment backup
create_backup() {
    log "Creating pre-deployment backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup database if containers are running
    if docker-compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
        log "Backing up PostgreSQL database..."
        docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U postgres google_news > "$BACKUP_DIR/database_backup.sql" || {
            warning "Database backup failed - continuing deployment"
        }
    fi
    
    # Backup Redis data if containers are running
    if docker-compose -f "$COMPOSE_FILE" ps redis | grep -q "Up"; then
        log "Backing up Redis data..."
        docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli --rdb - > "$BACKUP_DIR/redis_backup.rdb" || {
            warning "Redis backup failed - continuing deployment"
        }
    fi
    
    # Backup configuration
    cp -r data/ "$BACKUP_DIR/data_backup/" 2>/dev/null || true
    cp "$ENV_FILE" "$BACKUP_DIR/env_backup" 2>/dev/null || true
    
    success "Backup created in $BACKUP_DIR"
}

# Cleanup old backups
cleanup_backups() {
    log "Cleaning up old backups..."
    find ./backups -maxdepth 1 -type d -mtime +$MAX_BACKUP_DAYS -exec rm -rf {} \; 2>/dev/null || true
    success "Old backups cleaned up (older than $MAX_BACKUP_DAYS days)"
}

# Build production images
build_images() {
    log "Building production Docker images..."
    
    # Build with production target
    log "Building main application image..."
    docker build --target production -f docker/Dockerfile -t ${PROJECT_NAME}:latest -t ${PROJECT_NAME}:$(date +%Y%m%d) . || {
        error "Failed to build main application image"
        exit 1
    }
    
    log "Building worker image..."
    docker build --target production -f docker/Dockerfile.worker -t ${PROJECT_NAME}-worker:latest -t ${PROJECT_NAME}-worker:$(date +%Y%m%d) . || {
        error "Failed to build worker image"
        exit 1
    }
    
    success "Production images built successfully"
}

# Deploy with zero-downtime strategy
deploy_services() {
    log "Deploying services with zero-downtime strategy..."
    
    # Create necessary directories with proper permissions
    mkdir -p logs data/postgres data/redis data/beat data/ssl
    chown -R 1000:1000 logs data/ || warning "Could not set ownership for data directories"
    
    # Start database and Redis first if not running
    log "Ensuring database and Redis are running..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres redis
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    timeout=120
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec postgres pg_isready -U postgres -d google_news &> /dev/null; then
            success "Database is ready"
            break
        fi
        sleep 3
        ((timeout-=3))
    done
    
    if [ $timeout -le 0 ]; then
        error "Database failed to start within timeout"
        exit 1
    fi
    
    # Run migrations
    log "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" run --rm migration || {
        error "Database migration failed"
        exit 1
    }
    
    # Rolling update for application services
    log "Performing rolling update of application services..."
    
    # Update workers first (non-critical path)
    docker-compose -f "$COMPOSE_FILE" up -d --scale worker=0 worker
    sleep 5
    docker-compose -f "$COMPOSE_FILE" up -d --scale worker=3 worker
    
    # Update beat scheduler
    docker-compose -f "$COMPOSE_FILE" up -d beat
    
    # Update web services with rolling deployment
    docker-compose -f "$COMPOSE_FILE" up -d --scale web=1 web
    sleep 10  # Wait for new instance to be healthy
    docker-compose -f "$COMPOSE_FILE" up -d --scale web=2 web
    
    # Start nginx last
    docker-compose -f "$COMPOSE_FILE" up -d nginx
    
    # Start monitoring services
    docker-compose -f "$COMPOSE_FILE" up -d flower
    
    success "Services deployed successfully"
}

# Comprehensive health check
health_check() {
    log "Performing comprehensive health checks..."
    
    # Wait for services to stabilize
    sleep 30
    
    # Health check endpoints
    ENDPOINTS=(
        "http://localhost/health"
        "http://localhost/ready"
        "http://localhost/live"
    )
    
    for endpoint in "${ENDPOINTS[@]}"; do
        log "Checking $endpoint..."
        timeout=60
        while [ $timeout -gt 0 ]; do
            if curl -f -s "$endpoint" > /dev/null 2>&1; then
                success "$endpoint is healthy"
                break
            fi
            sleep 3
            ((timeout-=3))
        done
        
        if [ $timeout -le 0 ]; then
            error "$endpoint health check failed"
            return 1
        fi
    done
    
    # Check service status
    log "Checking service status..."
    docker-compose -f "$COMPOSE_FILE" ps
    
    # Check for any unhealthy containers
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "unhealthy\|Exit"; then
        error "Some containers are unhealthy or have exited"
        return 1
    fi
    
    success "All health checks passed"
}

# Security hardening post-deployment
security_hardening() {
    log "Applying security hardening..."
    
    # Remove development tools from containers if any
    # This is handled in Dockerfile, but we can add runtime hardening here
    
    # Set proper file permissions
    find data/ -type f -exec chmod 640 {} \; 2>/dev/null || true
    find data/ -type d -exec chmod 750 {} \; 2>/dev/null || true
    
    # Secure log files
    find logs/ -type f -exec chmod 640 {} \; 2>/dev/null || true
    
    success "Security hardening applied"
}

# Monitoring setup
setup_monitoring() {
    log "Setting up monitoring and alerting..."
    
    # Create monitoring configuration if it doesn't exist
    if [ ! -f "docker/fluent-bit.conf" ]; then
        warning "Log aggregation configuration not found. Skipping log monitoring setup."
    else
        # Start log aggregation if enabled
        if docker-compose -f "$COMPOSE_FILE" --profile logging ps log-aggregator | grep -q "Up" 2>/dev/null; then
            success "Log aggregation is running"
        else
            log "Starting log aggregation..."
            docker-compose -f "$COMPOSE_FILE" --profile logging up -d log-aggregator || {
                warning "Failed to start log aggregation"
            }
        fi
    fi
    
    success "Monitoring setup completed"
}

# Show production deployment info
show_production_info() {
    echo ""
    success "🎉 Production environment deployed successfully!"
    echo ""
    echo "📋 Service Information:"
    echo "  • Web API:         https://your-domain.com (or http://localhost if no SSL)"
    echo "  • Health Check:    https://your-domain.com/health"
    echo "  • Detailed Health: https://your-domain.com/health/detailed"
    echo "  • Flower Monitor:  https://your-domain.com/flower (if enabled)"
    echo ""
    echo "🔒 Security Features:"
    echo "  • Non-root containers"
    echo "  • Secrets management"
    echo "  • SSL/TLS encryption (if configured)"
    echo "  • Rate limiting"
    echo "  • Security headers"
    echo ""
    echo "📊 Monitoring:"
    echo "  • Container health checks"
    echo "  • Application metrics"
    echo "  • Log aggregation (if enabled)"
    echo ""
    echo "🛠️  Management Commands:"
    echo "  • View logs:       docker-compose -f $COMPOSE_FILE logs -f"
    echo "  • Scale workers:   docker-compose -f $COMPOSE_FILE up -d --scale worker=N"
    echo "  • Update service:  docker-compose -f $COMPOSE_FILE up -d SERVICE_NAME"
    echo "  • Backup:          ./scripts/deployment/backup-prod.sh"
    echo ""
}

# Rollback function
rollback() {
    error "Deployment failed. Initiating rollback..."
    
    if [ -d "$BACKUP_DIR" ]; then
        log "Rolling back to previous version..."
        
        # Stop current containers
        docker-compose -f "$COMPOSE_FILE" down
        
        # Restore database backup if exists
        if [ -f "$BACKUP_DIR/database_backup.sql" ]; then
            log "Restoring database backup..."
            docker-compose -f "$COMPOSE_FILE" up -d postgres
            sleep 10
            docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -d google_news < "$BACKUP_DIR/database_backup.sql"
        fi
        
        # Restore configuration
        if [ -f "$BACKUP_DIR/env_backup" ]; then
            cp "$BACKUP_DIR/env_backup" "$ENV_FILE"
        fi
        
        warning "Manual intervention may be required to complete rollback"
    else
        error "No backup found for rollback"
    fi
}

# Cleanup function
cleanup() {
    if [ $? -ne 0 ]; then
        rollback
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Main deployment flow
main() {
    echo "Starting production deployment..."
    
    security_check
    create_backup
    cleanup_backups
    build_images
    deploy_services
    
    if ! health_check; then
        error "Health checks failed. Deployment aborted."
        exit 1
    fi
    
    security_hardening
    setup_monitoring
    show_production_info
    
    success "Production deployment completed successfully!"
}

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "update")
        log "Updating services..."
        build_images
        deploy_services
        health_check
        success "Services updated"
        ;;
    "scale")
        if [ -z "$2" ] || [ -z "$3" ]; then
            error "Usage: $0 scale SERVICE_NAME REPLICAS"
            exit 1
        fi
        log "Scaling $2 to $3 replicas..."
        docker-compose -f "$COMPOSE_FILE" up -d --scale "$2=$3" "$2"
        success "Service $2 scaled to $3 replicas"
        ;;
    "stop")
        log "Stopping production services..."
        docker-compose -f "$COMPOSE_FILE" down
        success "Production services stopped"
        ;;
    "status")
        docker-compose -f "$COMPOSE_FILE" ps
        ;;
    "logs")
        docker-compose -f "$COMPOSE_FILE" logs -f "${2:-}"
        ;;
    "backup")
        create_backup
        success "Manual backup completed in $BACKUP_DIR"
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command] [args]"
        echo ""
        echo "Commands:"
        echo "  deploy           Deploy production environment (default)"
        echo "  update           Update services with new images"
        echo "  scale SERVICE N  Scale service to N replicas"
        echo "  stop             Stop all services"
        echo "  status           Show service status"
        echo "  logs [SERVICE]   Show logs"
        echo "  backup           Create manual backup"
        echo "  help             Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                    # Deploy production environment"
        echo "  $0 scale worker 5     # Scale workers to 5 replicas"
        echo "  $0 logs web           # Show web service logs"
        echo "  $0 backup             # Create manual backup"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for available commands"
        exit 1
        ;;
esac