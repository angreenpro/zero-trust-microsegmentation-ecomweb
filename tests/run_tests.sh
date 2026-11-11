# =====================================================================
#   bash tests/run_tests.sh              # Chạy toàn bộ KB0 -> KB4
#   bash tests/run_tests.sh kb1          # Chỉ chạy riêng KB1 (hoặc kb2, kb3, kb4)
#   bash tests/run_tests.sh --skip-kb4   # Bỏ qua KB4
# =====================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "   ZERO TRUST & MICRO-SEGMENTATION — AUTOMATED TEST RUNNER    "


echo -e "\n[1/3] Kiểm tra Docker Engine..."
if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon chưa chạy! Vui lòng bật Docker trước."
    exit 1
fi
echo " Docker Engine đang hoạt động."

echo -e "\n[2/3] Kiểm tra cụm 5 containers..."
RUNNING=$(docker ps --filter "name=mysql-db" --filter "name=auth-service" --filter "name=catalog-service" --filter "name=order-service" --filter "name=nginx-gateway" -q | wc -l)
if [ "$RUNNING" -lt 5 ]; then
    echo " Đang khởi động cụm container bằng docker-compose..."
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose up -d --build
    else
        docker compose up -d --build
    fi
fi

for i in {1..20}; do
    HEALTH=$(docker inspect --format "{{.State.Health.Status}}" mysql-db 2>/dev/null || echo "starting")
    if [ "$HEALTH" = "healthy" ]; then
        echo "Cụm 5 containers và mysql-db (healthy) đã sẵn sàng!"
        break
    fi
    sleep 2
done

echo -e "\n[3/3] Thực thi tests/run_scenarios.py..."
python "$SCRIPT_DIR/run_scenarios.py" "$@"

