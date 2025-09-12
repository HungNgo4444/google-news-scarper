#!/bin/bash

# Google News Scraper - Container Data Backup Script
# Comprehensive backup solution for containerized application data

set -e  # Exit on any error

echo "📦 Google News Scraper - Container Data Backup"
echo "=============================================="

# Configuration
PROJECT_NAME="google-news-scraper"
BACKUP_BASE_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE_DIR}/${TIMESTAMP}"
COMPOSE_FILE="${1:-docker-compose.yml}"
RETENTION_DAYS=${RETENTION_DAYS:-30}

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

# Create backup directory
setup_backup_dir() {
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    success "Backup directory created"
}

# Backup PostgreSQL database
backup_postgres() {
    log "Backing up PostgreSQL database..."
    
    if ! docker-compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
        warning "PostgreSQL container is not running. Skipping database backup."
        return 0
    fi
    
    # Get database connection details
    DB_NAME=$(docker-compose -f "$COMPOSE_FILE" exec -T postgres env | grep POSTGRES_DB | cut -d'=' -f2 | tr -d '\r')
    DB_USER=$(docker-compose -f "$COMPOSE_FILE" exec -T postgres env | grep POSTGRES_USER | cut -d'=' -f2 | tr -d '\r')
    
    if [ -z "$DB_NAME" ]; then
        DB_NAME="google_news"
    fi
    if [ -z "$DB_USER" ]; then
        DB_USER="postgres"
    fi
    
    # Create SQL dump
    log "Creating PostgreSQL dump for database: $DB_NAME"
    docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" --verbose --clean --create > "$BACKUP_DIR/postgres_backup.sql" || {
        error "PostgreSQL backup failed"
        return 1
    }
    
    # Create compressed backup
    gzip "$BACKUP_DIR/postgres_backup.sql"
    
    # Get database size info
    DB_SIZE=$(docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" | tr -d ' \r\n')
    
    success "PostgreSQL backup completed (Database size: $DB_SIZE)"
    echo "  • Backup file: postgres_backup.sql.gz"
}

# Backup Redis data
backup_redis() {
    log "Backing up Redis data..."
    
    if ! docker-compose -f "$COMPOSE_FILE" ps redis | grep -q "Up"; then
        warning "Redis container is not running. Skipping Redis backup."
        return 0
    fi
    
    # Create Redis dump using BGSAVE
    log "Creating Redis background save..."
    docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli BGSAVE
    
    # Wait for background save to complete
    while true; do
        LASTSAVE=$(docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli LASTSAVE | tr -d '\r')
        sleep 1
        CURRENT=$(docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli LASTSAVE | tr -d '\r')
        if [ "$LASTSAVE" != "$CURRENT" ]; then
            break
        fi
    done
    
    # Copy the RDB file
    docker-compose -f "$COMPOSE_FILE" exec -T redis cat /data/dump.rdb > "$BACKUP_DIR/redis_backup.rdb" || {
        error "Redis backup failed"
        return 1
    }
    
    # Get Redis info
    REDIS_MEMORY=$(docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli INFO memory | grep used_memory_human | cut -d':' -f2 | tr -d '\r')
    REDIS_KEYS=$(docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli DBSIZE | tr -d '\r')
    
    success "Redis backup completed (Memory: $REDIS_MEMORY, Keys: $REDIS_KEYS)"
    echo "  • Backup file: redis_backup.rdb"
}

# Backup Celery Beat schedule
backup_celery_beat() {
    log "Backing up Celery Beat schedule..."
    
    if ! docker-compose -f "$COMPOSE_FILE" ps beat | grep -q "Up"; then
        warning "Celery Beat container is not running. Skipping beat schedule backup."
        return 0
    fi
    
    # Copy beat schedule file if it exists
    if docker-compose -f "$COMPOSE_FILE" exec beat test -f /app/data/beat/celerybeat-schedule &> /dev/null; then
        docker-compose -f "$COMPOSE_FILE" exec -T beat cat /app/data/beat/celerybeat-schedule > "$BACKUP_DIR/celerybeat_schedule.dat" || {
            warning "Failed to backup Celery Beat schedule"
            return 0
        }
        success "Celery Beat schedule backed up"
        echo "  • Backup file: celerybeat_schedule.dat"
    else
        log "No Celery Beat schedule file found"
    fi
}

# Backup application logs
backup_logs() {
    log "Backing up application logs..."
    
    if [ ! -d "logs" ]; then
        warning "No logs directory found. Skipping log backup."
        return 0
    fi
    
    # Create logs backup directory
    mkdir -p "$BACKUP_DIR/logs"
    
    # Copy log files (last 7 days only to save space)
    find logs/ -type f -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/logs/" \; 2>/dev/null || true
    
    # Compress logs
    if [ "$(ls -A "$BACKUP_DIR/logs" 2>/dev/null)" ]; then
        tar -czf "$BACKUP_DIR/logs_backup.tar.gz" -C "$BACKUP_DIR" logs/
        rm -rf "$BACKUP_DIR/logs"
        
        LOG_SIZE=$(du -sh "$BACKUP_DIR/logs_backup.tar.gz" | cut -f1)
        success "Application logs backed up (Size: $LOG_SIZE)"
        echo "  • Backup file: logs_backup.tar.gz (last 7 days)"
    else
        log "No recent log files found"
    fi
}

# Backup volume data
backup_volumes() {
    log "Backing up Docker volumes..."
    
    # List volumes used by the compose file
    VOLUMES=$(docker-compose -f "$COMPOSE_FILE" config --volumes 2>/dev/null || true)
    
    if [ -z "$VOLUMES" ]; then
        warning "No named volumes found. Skipping volume backup."
        return 0
    fi
    
    mkdir -p "$BACKUP_DIR/volumes"
    
    for VOLUME in $VOLUMES; do
        log "Backing up volume: $VOLUME"
        
        # Create a temporary container to backup volume
        docker run --rm -v "${PROJECT_NAME}_${VOLUME}:/data" -v "$PWD/$BACKUP_DIR/volumes:/backup" alpine:latest tar -czf "/backup/${VOLUME}.tar.gz" -C /data . || {
            warning "Failed to backup volume: $VOLUME"
            continue
        }
        
        VOLUME_SIZE=$(du -sh "$BACKUP_DIR/volumes/${VOLUME}.tar.gz" 2>/dev/null | cut -f1 || echo "unknown")
        success "Volume $VOLUME backed up (Size: $VOLUME_SIZE)"
    done
}

# Backup configuration files
backup_config() {
    log "Backing up configuration files..."
    
    mkdir -p "$BACKUP_DIR/config"
    
    # Backup compose files
    cp docker-compose*.yml "$BACKUP_DIR/config/" 2>/dev/null || true
    
    # Backup environment files (excluding sensitive production env)
    cp .env.example "$BACKUP_DIR/config/" 2>/dev/null || true
    cp .env "$BACKUP_DIR/config/env_development.backup" 2>/dev/null || true
    
    # Backup Docker configuration
    cp -r docker/ "$BACKUP_DIR/config/" 2>/dev/null || true
    
    # Backup application configuration
    cp alembic.ini "$BACKUP_DIR/config/" 2>/dev/null || true
    cp pytest.ini "$BACKUP_DIR/config/" 2>/dev/null || true
    cp requirements.txt "$BACKUP_DIR/config/" 2>/dev/null || true
    
    success "Configuration files backed up"
}

# Create backup metadata
create_metadata() {
    log "Creating backup metadata..."
    
    cat > "$BACKUP_DIR/backup_info.json" << EOF
{
    "backup_timestamp": "$TIMESTAMP",
    "backup_date": "$(date -Iseconds)",
    "project_name": "$PROJECT_NAME",
    "compose_file": "$COMPOSE_FILE",
    "hostname": "$(hostname)",
    "docker_version": "$(docker --version)",
    "compose_version": "$(docker-compose --version)",
    "services_status": $(docker-compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null || echo '[]'),
    "backup_components": [
        "postgres",
        "redis", 
        "celery_beat",
        "logs",
        "volumes",
        "configuration"
    ]
}
EOF
    
    # Create human-readable summary
    cat > "$BACKUP_DIR/README.md" << EOF
# Google News Scraper Backup

**Backup Created:** $(date)  
**Backup ID:** $TIMESTAMP  
**Compose File:** $COMPOSE_FILE  

## Backup Contents

- \`postgres_backup.sql.gz\` - PostgreSQL database dump
- \`redis_backup.rdb\` - Redis data snapshot
- \`celerybeat_schedule.dat\` - Celery Beat scheduler state
- \`logs_backup.tar.gz\` - Application logs (last 7 days)
- \`volumes/\` - Docker volume backups
- \`config/\` - Configuration files and Docker setup
- \`backup_info.json\` - Backup metadata

## Restore Instructions

1. Stop the current application:
   \`\`\`bash
   docker-compose -f $COMPOSE_FILE down
   \`\`\`

2. Restore database:
   \`\`\`bash
   gunzip postgres_backup.sql.gz
   docker-compose -f $COMPOSE_FILE up -d postgres
   docker-compose -f $COMPOSE_FILE exec -T postgres psql -U postgres < postgres_backup.sql
   \`\`\`

3. Restore Redis:
   \`\`\`bash
   docker-compose -f $COMPOSE_FILE up -d redis
   docker-compose -f $COMPOSE_FILE exec -T redis redis-cli FLUSHALL
   docker cp redis_backup.rdb \$(docker-compose -f $COMPOSE_FILE ps -q redis):/data/dump.rdb
   docker-compose -f $COMPOSE_FILE restart redis
   \`\`\`

4. Restore configuration and restart services:
   \`\`\`bash
   # Restore configuration files as needed
   docker-compose -f $COMPOSE_FILE up -d
   \`\`\`

**Note:** Always test restores in a non-production environment first.
EOF
    
    success "Backup metadata created"
}

# Calculate backup size and create summary
create_summary() {
    log "Creating backup summary..."
    
    BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
    FILE_COUNT=$(find "$BACKUP_DIR" -type f | wc -l)
    
    echo ""
    success "🎉 Backup completed successfully!"
    echo ""
    echo "📦 Backup Information:"
    echo "  • Backup ID:      $TIMESTAMP"
    echo "  • Location:       $BACKUP_DIR"
    echo "  • Total Size:     $BACKUP_SIZE"
    echo "  • Files:          $FILE_COUNT"
    echo "  • Created:        $(date)"
    echo ""
    echo "📋 Backup Contents:"
    ls -la "$BACKUP_DIR" | tail -n +2 | while read line; do
        echo "  • $line"
    done
    echo ""
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups (older than $RETENTION_DAYS days)..."
    
    if [ -d "$BACKUP_BASE_DIR" ]; then
        find "$BACKUP_BASE_DIR" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
        
        REMAINING_BACKUPS=$(find "$BACKUP_BASE_DIR" -maxdepth 1 -type d | wc -l)
        success "Old backups cleaned up. $REMAINING_BACKUPS backup(s) remaining."
    fi
}

# Main backup function
main() {
    echo "Starting container data backup..."
    
    setup_backup_dir
    
    # Perform individual backups
    backup_postgres
    backup_redis
    backup_celery_beat
    backup_logs
    backup_volumes
    backup_config
    
    create_metadata
    create_summary
    cleanup_old_backups
    
    success "Container backup process completed!"
}

# Restore function
restore() {
    local BACKUP_ID="$1"
    
    if [ -z "$BACKUP_ID" ]; then
        error "Usage: $0 restore BACKUP_ID"
        echo "Available backups:"
        ls -la "$BACKUP_BASE_DIR" | tail -n +2 | grep "^d"
        exit 1
    fi
    
    local RESTORE_DIR="${BACKUP_BASE_DIR}/${BACKUP_ID}"
    
    if [ ! -d "$RESTORE_DIR" ]; then
        error "Backup not found: $RESTORE_DIR"
        exit 1
    fi
    
    warning "This will restore data from backup: $BACKUP_ID"
    warning "Current data may be overwritten. Continue? (y/N)"
    read -r CONFIRM
    
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        log "Restore cancelled"
        exit 0
    fi
    
    log "Starting restore from backup: $BACKUP_ID"
    
    # Stop services
    log "Stopping services..."
    docker-compose -f "$COMPOSE_FILE" down
    
    # Restore database
    if [ -f "$RESTORE_DIR/postgres_backup.sql.gz" ]; then
        log "Restoring PostgreSQL database..."
        docker-compose -f "$COMPOSE_FILE" up -d postgres
        sleep 10
        gunzip -c "$RESTORE_DIR/postgres_backup.sql.gz" | docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres
        success "PostgreSQL database restored"
    fi
    
    # Restore Redis
    if [ -f "$RESTORE_DIR/redis_backup.rdb" ]; then
        log "Restoring Redis data..."
        docker-compose -f "$COMPOSE_FILE" up -d redis
        sleep 5
        docker-compose -f "$COMPOSE_FILE" exec redis redis-cli FLUSHALL
        docker cp "$RESTORE_DIR/redis_backup.rdb" "$(docker-compose -f "$COMPOSE_FILE" ps -q redis):/data/dump.rdb"
        docker-compose -f "$COMPOSE_FILE" restart redis
        success "Redis data restored"
    fi
    
    # Start all services
    log "Starting all services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    success "Restore completed successfully!"
}

# List available backups
list_backups() {
    echo "Available backups:"
    echo ""
    
    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        warning "No backup directory found"
        exit 0
    fi
    
    for backup_dir in "$BACKUP_BASE_DIR"/*; do
        if [ -d "$backup_dir" ]; then
            local backup_id=$(basename "$backup_dir")
            local backup_size=$(du -sh "$backup_dir" 2>/dev/null | cut -f1 || echo "unknown")
            local backup_date=$(date -r "$backup_dir" 2>/dev/null || echo "unknown")
            
            echo "📦 $backup_id"
            echo "   Size: $backup_size"
            echo "   Date: $backup_date"
            
            if [ -f "$backup_dir/backup_info.json" ]; then
                local compose_file=$(cat "$backup_dir/backup_info.json" | grep '"compose_file"' | cut -d'"' -f4)
                echo "   Compose: $compose_file"
            fi
            echo ""
        fi
    done
}

# Parse command line arguments
case "${1:-backup}" in
    "backup")
        main
        ;;
    "restore")
        restore "$2"
        ;;
    "list")
        list_backups
        ;;
    "cleanup")
        cleanup_old_backups
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command] [args]"
        echo ""
        echo "Commands:"
        echo "  backup           Create a full backup (default)"
        echo "  restore ID       Restore from backup ID"
        echo "  list             List available backups"
        echo "  cleanup          Clean up old backups"
        echo "  help             Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  RETENTION_DAYS   Number of days to keep backups (default: 30)"
        echo ""
        echo "Examples:"
        echo "  $0                           # Create backup"
        echo "  $0 restore 20241201_143022   # Restore from backup"
        echo "  $0 list                      # List backups"
        echo "  RETENTION_DAYS=7 $0 cleanup  # Keep only 7 days"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for available commands"
        exit 1
        ;;
esac