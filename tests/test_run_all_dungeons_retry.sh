#!/bin/bash
# 测试 run_all_dungeons.sh 的重试逻辑

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RUN_ALL_DUNGEONS="$PROJECT_ROOT/run_all_dungeons.sh"

# 测试 1: 验证重试逻辑存在
test_retry_logic_exists() {
    print_info "测试 1: 验证重试逻辑存在..."

    if grep -q "max_retries=3" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 找到 max_retries=3"
    else
        print_error "✗ 未找到 max_retries=3"
        return 1
    fi

    if grep -q "retry_count" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 找到 retry_count 变量"
    else
        print_error "✗ 未找到 retry_count 变量"
        return 1
    fi

    if grep -q "while \[ \$retry_count -lt \$max_retries \]" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 找到重试循环"
    else
        print_error "✗ 未找到重试循环"
        return 1
    fi
}

# 测试 2: 验证等待时间逻辑
test_wait_time_logic() {
    print_info "测试 2: 验证等待时间逻辑..."

    if grep -q "wait_time=\$((retry_count \* 10))" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 找到指数退避等待时间计算"
    else
        print_error "✗ 未找到指数退避等待时间计算"
        return 1
    fi
}

# 测试 3: 验证错误消息
test_error_messages() {
    print_info "测试 3: 验证错误消息..."

    if grep -q "第 \$retry_count/\$max_retries 次失败" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 找到重试次数显示"
    else
        print_error "✗ 未找到重试次数显示"
        return 1
    fi

    if grep -q "在 \$max_retries 次重试后仍然失败" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 找到最终失败消息"
    else
        print_error "✗ 未找到最终失败消息"
        return 1
    fi
}

# 测试 4: 验证帮助信息更新
test_help_info_updated() {
    print_info "测试 4: 验证帮助信息更新..."

    if grep -q "每个角色最多重试 3 次" "$RUN_ALL_DUNGEONS"; then
        print_success "✓ 帮助信息中包含重试说明"
    else
        print_error "✗ 帮助信息中缺少重试说明"
        return 1
    fi
}

# 主测试函数
main() {
    print_info "开始测试 run_all_dungeons.sh 的重试逻辑..."
    echo ""

    local failed=0

    test_retry_logic_exists || ((failed++))
    echo ""

    test_wait_time_logic || ((failed++))
    echo ""

    test_error_messages || ((failed++))
    echo ""

    test_help_info_updated || ((failed++))
    echo ""

    if [ $failed -eq 0 ]; then
        print_success "所有测试通过！"
        return 0
    else
        print_error "有 $failed 个测试失败"
        return 1
    fi
}

main "$@"

