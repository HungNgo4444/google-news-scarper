#!/bin/bash

# Google News Scraper - Development Deployment Script
# This script sets up the complete development environment using Docker Compose

set -e  # Exit on any error

echo "🚀 Google News Scraper - Development Deployment"
echo "================================================"

# Configuration
PROJECT_NAME="google-news-scraper"
ENV_FILE=".env"
COMPOSE_FILE="docker-compose.yml"

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Setup environment
setup_environment() {
    log "Setting up environment..."
    
    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example "$ENV_FILE"
            success "Created $ENV_FILE from .env.example"
        else
            error ".env.example file not found. Cannot create environment configuration."
            exit 1
        fi
    else
        success "Environment file $ENV_FILE already exists"
    fi
    
    # Create necessary directories
    mkdir -p logs data/postgres data/redis data/beat
    success "Created necessary directories"
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    # Build main application image
    log "Building main application image..."
    docker build -f docker/Dockerfile -t ${PROJECT_NAME}:latest . || {
        error "Failed to build main application image"
        exit 1
    }
    
    # Build worker image
    log "Building worker image..."
    docker build -f docker/Dockerfile.worker -t ${PROJECT_NAME}-worker:latest . || {
        error "Failed to build worker image"
        exit 1
    }
    
    success "Docker images built successfully"
}

# Start services
start_services() {
    log "Starting services..."
    
    # Stop any running containers first
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans
    
    # Start services with dependency order
    log "Starting database and Redis..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres redis
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec postgres pg_isready -U postgres -d google_news &> /dev/null; then
            success "Database is ready"
            break
        fi
        sleep 2
        ((timeout-=2))
    done
    
    if [ $timeout -le 0 ]; then
        error "Database failed to start within timeout"
        exit 1
    fi
    
    # Run database migrations
    log "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" run --rm migration || {
        error "Database migration failed"
        exit 1
    }
    
    # Start application services
    log "Starting application services..."
    docker-compose -f "$COMPOSE_FILE" up -d web worker beat
    
    success "All services started"
}

# Health check
health_check() {
    log "Performing health checks..."
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 10
    
    # Check web service
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            success "Web service is healthy"
            break
        fi
        sleep 2
        ((timeout-=2))
    done
    
    if [ $timeout -le 0 ]; then
        warning "Web service health check timeout - check logs"
    fi
    
    # Show service status
    log "Service status:"
    docker-compose -f "$COMPOSE_FILE" ps
}

# Show deployment info
show_info() {
    echo ""
    success "🎉 Development environment deployed successfully!"
    echo ""
    echo "📋 Service Information:"
    echo "  • Web API:        http://localhost:8000"
    echo "  • API Docs:       http://localhost:8000/api/v1/docs"
    echo "  • Health Check:   http://localhost:8000/health"
    echo "  • Database:       localhost:5432 (postgres/postgres)"
    echo "  • Redis:          localhost:6379"
    echo ""
    echo "🛠️  Useful Commands:"
    echo "  • View logs:      docker-compose logs -f"
    echo "  • Stop services:  docker-compose down"
    echo "  • Restart:        docker-compose restart"
    echo "  • Shell access:   docker-compose exec web bash"
    echo ""
    echo "📁 Data Locations:"
    echo "  • Logs:           ./logs/"
    echo "  • PostgreSQL:     ./data/postgres/"
    echo "  • Redis:          ./data/redis/"
    echo ""
}

# Cleanup function
cleanup() {
    if [ $? -ne 0 ]; then
        error "Deployment failed. Cleaning up..."
        docker-compose -f "$COMPOSE_FILE" down --remove-orphans
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Main deployment flow
main() {
    echo "Starting development deployment..."
    
    check_prerequisites
    setup_environment
    build_images
    start_services
    health_check
    show_info
    
    success "Development deployment completed!"
}

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log "Stopping services..."
        docker-compose -f "$COMPOSE_FILE" down
        success "Services stopped"
        ;;
    "restart")
        log "Restarting services..."
        docker-compose -f "$COMPOSE_FILE" restart
        success "Services restarted"
        ;;
    "logs")
        docker-compose -f "$COMPOSE_FILE" logs -f "${2:-}"
        ;;
    "status")
        docker-compose -f "$COMPOSE_FILE" ps
        ;;
    "clean")
        log "Cleaning up containers and volumes..."
        docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
        docker system prune -f
        success "Cleanup completed"
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  deploy    Deploy development environment (default)"
        echo "  stop      Stop all services"
        echo "  restart   Restart all services"
        echo "  logs      Show logs (optionally specify service)"
        echo "  status    Show service status"
        echo "  clean     Clean up containers and volumes"
        echo "  help      Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                  # Deploy development environment"
        echo "  $0 logs web         # Show web service logs"
        echo "  $0 stop             # Stop all services"
        echo "  $0 clean            # Clean up everything"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for available commands"
        exit 1
        ;;
esac