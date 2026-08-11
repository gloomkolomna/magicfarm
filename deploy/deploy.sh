#!/bin/bash
#
# Деплой системы «Ферма» на прод.
#
# Адаптация deploy/deploy.sh из «Затерянный мир» (конвенции 1:1).
# Различия: пути /opt/farm, порт 8003, префикс /farm/, бота пока нет.
#
# Режим восстановления (флаг -recovery / --recovery):
#   ./deploy.sh -recovery
#   Интерактивное восстановление проекта из tar-архива (farm_full_*.tar.gz).
#   Перед распаковкой создаёт резервную копию ТЕКУЩЕГО состояния
#   (farm_pre_recovery_<ts>.tar.gz), чтобы можно было откатиться.
#
# Обычный деплой (без флагов):
#   ./deploy.sh
#   1. Фиксируем текущую ревизию Alembic (точка отката БД) и git (точка отката кода).
#   2. Полный архив проекта (код + БД + dist + .env) ДО изменений.
#      Ротация 5 архивов в /opt/farm-backups. Бэкап БД строго до миграции.
#      Бэкап dist (фронтенд) до сборки.
#   3. git pull.
#   4. alembic upgrade head.
#   5. Сборка фронта + рестарт сервиса farm-api.
#      (farm-bot пока не реализован — шаг закомментирован, см. TODO.)
#   6. Health-check после рестарта.
#   7. При ЛЮБОЙ ошибке на этапах 3–6:
#      — откат БД (downgrade или бэкап)
#      — откат кода (git reset --hard)
#      — восстановление старого dist (фронтенда)
#      — переустановка зависимостей от старой версии
#      — рестарт сервиса
#

set -euo pipefail

# ===== Парсинг аргументов: режим восстановления =====
RECOVERY_MODE=0
for arg in "$@"; do
    case "$arg" in
        -recovery|--recovery)
            RECOVERY_MODE=1
            ;;
        -help|--help|-h)
            echo "Использование: deploy.sh [-recovery]"
            echo "  без флагов            — обычный деплой"
            echo "  -recovery, --recovery — восстановить проект из tar-архива (интерактивно)"
            exit 0
            ;;
    esac
done

# ===== Режим восстановления из tar-архива =====
if [ "$RECOVERY_MODE" -eq 1 ]; then
    RECOVERY_BACKUP_DIR="/opt/farm-backups"
    RECOVERY_APP_PARENT="/opt"
    RECOVERY_APP_NAME="farm"
    RECOVERY_LOG="/opt/farm-backups/recovery.log"

    mkdir -p "$RECOVERY_BACKUP_DIR"

    _recovery_log() {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RECOVERY_LOG"
    }

    _recovery_log "=== ВОССТАНОВЛЕНИЕ ПРОЕКТА ИЗ АРХИВА ==="

    mapfile -t ARCHIVES < <(ls -1t "$RECOVERY_BACKUP_DIR"/farm_full_*.tar.gz 2>/dev/null || true)
    if [ "${#ARCHIVES[@]}" -eq 0 ]; then
        _recovery_log "ОШИБКА: архивы не найдены в $RECOVERY_BACKUP_DIR/farm_full_*.tar.gz"
        echo "Нет доступных архивов для восстановления."
        exit 1
    fi

    echo ""
    echo "Доступные архивы (новейшие сверху):"
    echo "-----------------------------------"
    for i in "${!ARCHIVES[@]}"; do
        arc="${ARCHIVES[$i]}"
        size=$(du -h "$arc" | cut -f1)
        printf "  [%d] %s  (%s)\n" "$((i+1))" "$(basename "$arc")" "$size"
    done
    echo "-----------------------------------"
    echo ""

    while true; do
        read -r -p "Выбери номер архива [1-${#ARCHIVES[@]}]: " CHOICE
        if [[ "$CHOICE" =~ ^[0-9]+$ ]] && [ "$CHOICE" -ge 1 ] && [ "$CHOICE" -le "${#ARCHIVES[@]}" ]; then
            SELECTED_ARCHIVE="${ARCHIVES[$((CHOICE-1))]}"
            break
        fi
        echo "Неверный номер. Попробуй ещё раз."
    done

    echo ""
    echo "Выбран архив: $SELECTED_ARCHIVE"
    echo "ВНИМАНИЕ: текущее состояние проекта ($RECOVERY_APP_PARENT/$RECOVERY_APP_NAME) будет заменено."
    echo "          Перед этим будет создан резервный архив текущего состояния."
    echo ""
    read -r -p "Продолжить восстановление? [y/N]: " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[YyДд]$ ]]; then
        _recovery_log "Восстановление отменено пользователем."
        echo "Отменено."
        exit 0
    fi

    PRE_RECOVERY_ARCHIVE="$RECOVERY_BACKUP_DIR/farm_pre_recovery_$(date '+%Y%m%d_%H%M%S').tar.gz"
    _recovery_log "Создаю резервную копию текущего состояния: $PRE_RECOVERY_ARCHIVE ..."
    if tar -czf "$PRE_RECOVERY_ARCHIVE" \
        --exclude="$RECOVERY_APP_PARENT/$RECOVERY_APP_NAME/api/venv" \
        --exclude="$RECOVERY_APP_PARENT/$RECOVERY_APP_NAME/frontend/node_modules" \
        --exclude="$RECOVERY_APP_PARENT/$RECOVERY_APP_NAME/.git" \
        --exclude="$RECOVERY_APP_PARENT/$RECOVERY_APP_NAME/api/backups" \
        --exclude="$RECOVERY_APP_PARENT/$RECOVERY_APP_NAME/frontend/tsconfig.tsbuildinfo" \
        --exclude='*.log' \
        -C "$RECOVERY_APP_PARENT" "$RECOVERY_APP_NAME" 2>/dev/null; then
        _recovery_log "Резервная копия текущего состояния создана: $PRE_RECOVERY_ARCHIVE ($(du -h "$PRE_RECOVERY_ARCHIVE" | cut -f1))"
    else
        _recovery_log "ОШИБКА: не удалось создать резервную копию текущего состояния. Восстановление прервано (проект не тронут)."
        rm -f "$PRE_RECOVERY_ARCHIVE" 2>/dev/null || true
        echo "ОШИБКА: не удалось создать резервную копию. Отменено, проект не тронут."
        exit 1
    fi

    _recovery_log "Останавливаю сервис farm-api..."
    systemctl stop farm-api 2>/dev/null || true
    sleep 2

    _recovery_log "Восстанавливаю из архива: $SELECTED_ARCHIVE ..."
    if ! tar -xzf "$SELECTED_ARCHIVE" -C "$RECOVERY_APP_PARENT"; then
        _recovery_log "ОШИБКА: распаковка не удалась. Текущее состояние сохранено в $PRE_RECOVERY_ARCHIVE."
        echo "ОШИБКА: распаковка не удалась. Откат: $PRE_RECOVERY_ARCHIVE"
        systemctl start farm-api 2>/dev/null || true
        exit 1
    fi
    _recovery_log "Архив распакован."

    _recovery_log "Переустанавливаю Python-зависимости..."
    cd "$RECOVERY_APP_PARENT/$RECOVERY_APP_NAME/api"
    if [ -d "venv" ]; then
        source venv/bin/activate
        pip install -r requirements.txt || _recovery_log "ПРЕДУПРЕЖДЕНИЕ: pip install завершился с ошибкой (не критично, продолжаю)."
    else
        _recovery_log "ПРЕДУПРЕЖДЕНИЕ: venv не найден. Зависимости не переустановлены."
    fi

    _recovery_log "Запускаю сервис farm-api..."
    systemctl start farm-api 2>/dev/null || true
    sleep 3

    ls -1t "$RECOVERY_BACKUP_DIR"/farm_pre_recovery_*.tar.gz 2>/dev/null | tail -n +6 | while read -r old; do
        rm -f "$old"
        _recovery_log "Удалён старый pre_recovery архив: $old"
    done

    _recovery_log "=== ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО ==="
    _recovery_log "API: $(systemctl is-active farm-api || true)."
    _recovery_log "Если что-то не так — откат: tar -xzf $PRE_RECOVERY_ARCHIVE -C $RECOVERY_APP_PARENT"
    echo ""
    echo "=== Восстановление завершено ==="
    echo "Статус сервиса: API=$(systemctl is-active farm-api || echo 'не активен')"
    echo "Резервная копия текущего состояния (до восстановления): $PRE_RECOVERY_ARCHIVE"
    exit 0
fi

# ===== Конфигурация =====
APP_DIR="/opt/farm"
API_DIR="$APP_DIR/api"
FRONTEND_DIR="$APP_DIR/frontend"
DB_FILE="$API_DIR/farm.db"
BACKUP_DIR="$API_DIR/backups"
BACKUPS_TO_KEEP=10
FULL_BACKUP_DIR="/opt/farm-backups"
FULL_BACKUPS_TO_KEEP=5
GIT_REMOTE="https://github.com/gloomkolomna/farm"   # ЗАМЕНИ, если репозиторий другой
GIT_BRANCH="main"
HEALTH_URL="http://127.0.0.1:8003/api/"              # через nginx — поменяй на домен/путь
LOG_FILE="$API_DIR/deploy.log"

# Флаги состояния
PREV_REV=""
PREV_GIT=""
FRESH_DEPLOY=0
BACKUP_PATH=""
DIST_BACKUP_PATH=""
MIGRATION_RAN=0
BUILD_RAN=0
SERVICES_RESTARTED=0

mkdir -p "$BACKUP_DIR"
mkdir -p "$FULL_BACKUP_DIR"

# ===== Логирование =====
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ===== Откат БД =====
rollback_db() {
    log "ОТКАТ: попытка вернуться к ревизии '$PREV_REV'..."

    if [ "$MIGRATION_RAN" -eq 1 ] && [ -n "$PREV_REV" ] && [ "$FRESH_DEPLOY" -eq 0 ]; then
        cd "$API_DIR"
        source venv/bin/activate
        if python -m alembic downgrade "$PREV_REV"; then
            log "ОТКАТ: успешный downgrade к '$PREV_REV'."
            return 0
        fi
        log "ОТКАТ: downgrade не удался, переходим к восстановлению из бэкапа."
    fi

    if [ -n "$BACKUP_PATH" ] && [ -f "$BACKUP_PATH" ]; then
        log "ОТКАТ: восстановление БД из '$BACKUP_PATH'..."
        cp "$BACKUP_PATH" "$DB_FILE"
        log "ОТКАТ: БД восстановлена из бэкапа."
        return 0
    fi

    log "ОТКАТ: нет ни точки отката, ни бэкапа — состояние БД неизвестно, требуется ручное вмешательство!"
    return 1
}

# ===== Полный откат: БД + код + фронтенд + сервисы =====
rollback_all() {
    log "=== ПОЛНЫЙ ОТКАТ ВСЕХ КОМПОНЕНТОВ ==="

    rollback_db || log "ОТКАТ: не удалось полностью откатить БД."

    if [ -n "$PREV_GIT" ]; then
        log "ОТКАТ: сброс git к '$PREV_GIT'..."
        cd "$APP_DIR"
        git reset --hard "$PREV_GIT"
        git clean -fd 2>/dev/null || true
        log "ОТКАТ: git сброшен к '$PREV_GIT'."
    else
        log "ОТКАТ: предыдущая git-ревизия неизвестна, пропускаю сброс кода."
    fi

    log "ОТКАТ: переустановка Python-зависимостей..."
    cd "$API_DIR"
    source venv/bin/activate
    pip install -r requirements.txt || log "ОТКАТ: pip install завершился с ошибкой (не критично)."

    if [ -n "$DIST_BACKUP_PATH" ] && [ -d "$DIST_BACKUP_PATH" ]; then
        log "ОТКАТ: восстановление старого фронтенда из '$DIST_BACKUP_PATH'..."
        rm -rf "$FRONTEND_DIR/dist"
        mv "$DIST_BACKUP_PATH" "$FRONTEND_DIR/dist"
    fi

    log "ОТКАТ: перезапуск сервиса farm-api..."
    systemctl restart farm-api || true

    rm -rf "$FRONTEND_DIR/dist.bak" 2>/dev/null || true

    log "ОТКАТ завершён. API: $(systemctl is-active farm-api || true)."
}

# ===== Ловушка ошибок =====
on_error() {
    local exit_code=$?
    log "ДЕПЛОЙ ПРОВАЛЕН (код $exit_code). Запускаю полный откат..."
    trap - ERR
    rollback_all
    log "Деплой завершён с ошибкой. API: $(systemctl is-active farm-api || true)."
}
trap on_error ERR

# ===== 1. Текущая ревизия БД + git =====
log "=== 1. Фиксация текущего состояния ==="
cd "$APP_DIR"

PREV_GIT=$(git rev-parse HEAD 2>/dev/null || echo "")
if [ -n "$PREV_GIT" ]; then
    log "Git-ревизия до деплоя: $PREV_GIT"
else
    log "Не удалось определить текущую git-ревизию."
fi

cd "$API_DIR"
source venv/bin/activate

PREV_REV=$(python -m alembic current 2>/dev/null | awk '{print $1}' | head -n1)
if [ -z "$PREV_REV" ]; then
    log "Текущая ревизия БД не определена (пустая/новая БД)."
    FRESH_DEPLOY=1
else
    log "Текущая ревизия БД: $PREV_REV"
fi

# ===== 2. Бэкап БД + dist =====
log "=== 2. Резервное копирование ==="

FULL_ARCHIVE="$FULL_BACKUP_DIR/farm_full_$(date '+%Y%m%d_%H%M%S').tar.gz"
if tar -czf "$FULL_ARCHIVE" \
    --exclude="$APP_DIR/api/venv" \
    --exclude="$APP_DIR/frontend/node_modules" \
    --exclude="$APP_DIR/.git" \
    --exclude="$APP_DIR/api/backups" \
    --exclude="$APP_DIR/frontend/tsconfig.tsbuildinfo" \
    --exclude='*.log' \
    -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")" 2>/dev/null; then
    log "Полный архив создан: $FULL_ARCHIVE ($(du -h "$FULL_ARCHIVE" | cut -f1))"

    ls -1t "$FULL_BACKUP_DIR"/farm_full_*.tar.gz 2>/dev/null | tail -n +$((FULL_BACKUPS_TO_KEEP + 1)) | while read -r old; do
        rm -f "$old"
        log "Удалён старый полный архив: $old"
    done
else
    log "ВНИМАНИЕ: не удалось создать полный архив '$FULL_ARCHIVE'. Деплой продолжится, но точки полного отката не будет."
    rm -f "$FULL_ARCHIVE" 2>/dev/null || true
fi

if [ -f "$DB_FILE" ]; then
    BACKUP_PATH="$BACKUP_DIR/farm.db.bak.$(date '+%Y%m%d_%H%M%S')"
    cp "$DB_FILE" "$BACKUP_PATH"
    log "Бэкап БД создан: $BACKUP_PATH ($(du -h "$BACKUP_PATH" | cut -f1))"

    ls -1t "$BACKUP_DIR"/farm.db.bak.* 2>/dev/null | tail -n +$((BACKUPS_TO_KEEP + 1)) | while read -r old; do
        rm -f "$old"
        log "Удалён старый бэкап: $old"
    done
else
    log "Внимание: файл БД '$DB_FILE' не найден — бэкап пропущен."
    BACKUP_PATH=""
fi

if [ -d "$FRONTEND_DIR/dist" ]; then
    DIST_BACKUP_PATH="$FRONTEND_DIR/dist.bak"
    rm -rf "$DIST_BACKUP_PATH"
    cp -r "$FRONTEND_DIR/dist" "$DIST_BACKUP_PATH"
    log "Бэкап dist создан: $DIST_BACKUP_PATH"
fi

# ===== 3. Git pull =====
log "=== 3. Git pull ==="
cd "$APP_DIR"
rm -f frontend/tsconfig.tsbuildinfo
git fetch "$GIT_REMOTE" "$GIT_BRANCH"
git reset --hard FETCH_HEAD

# ===== 4. Зависимости + миграции =====
log "=== 4. Установка зависимостей и миграции ==="
cd "$API_DIR"
source venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
MIGRATION_RAN=1
log "Миграции применены. Текущая ревизия: $(python -m alembic current 2>/dev/null | awk '{print $1}' | head -n1)"

# ===== 5. Сборка фронтенда =====
log "=== 5. Сборка фронтенда ==="
cd "$FRONTEND_DIR"
rm -rf "$FRONTEND_DIR/dist"
npm install
npm run build
BUILD_RAN=1

# ===== 6. Перезапуск сервиса =====
log "=== 6. Перезапуск сервиса ==="
systemctl restart farm-api
SERVICES_RESTARTED=1
sleep 3
systemctl status farm-api --no-pager | tee -a "$LOG_FILE" || true

# ===== 7. Health-check =====
log "=== 7. Health-check ==="
HEALTH_OK=0
for i in 1 2 3 4 5; do
    if curl -fsS -o /dev/null "$HEALTH_URL"; then
        HEALTH_OK=1
        break
    fi
    log "Health-check попытка $i/5 неудачна, ждём..."
    sleep 3
done

if [ "$HEALTH_OK" -ne 1 ]; then
    log "Health-check провалился — запускаю откат."
    false
fi

log "=== Деплой успешно завершён ==="

rm -rf "$DIST_BACKUP_PATH" 2>/dev/null || true
