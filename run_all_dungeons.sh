#!/bin/zsh
# 运行所有角色的自动化副本脚本
# 使用方法: ./run_all_dungeons.sh [选项] [角色名称]
# 如果不指定角色名称，则依次运行所有角色

# 注意：不使用 set -e，以便在单个角色失败后继续运行其他角色

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
export PATH="/opt/homebrew/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 所有可用的角色配置
CHARACTERS=(
    "paladin"
    "mage"
    "rogue"
    "hunter"
    "warlock"
    "druid"
    "monk"
    "shaman"
    "priest"
    "deathknight"
    "warrior"
)

# 角色中文名称映射
declare -A CHARACTER_NAMES=(
    ["warrior"]="战士"
    ["paladin"]="圣骑士"
    ["mage"]="法师"
    ["rogue"]="盗贼"
    ["hunter"]="猎人"
    ["warlock"]="术士"
    ["druid"]="德鲁伊"
    ["monk"]="武僧"
    ["shaman"]="萨满祭司"
    ["priest"]="牧师"
    ["deathknight"]="死亡骑士"
)

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 运行单个角色的副本（带重试逻辑）
run_character() {
    local character=$1
    local emulator=$2
    shift 2
    local env_overrides=("$@")  # 剩余的参数作为环境变量覆盖
    local config_file="configs/${character}.json"
    local character_name=${CHARACTER_NAMES[$character]:-$character}
    local max_retries=3  # 最多重试 3 次
    local retry_count=0

    if [ ! -f "$config_file" ]; then
        print_error "配置文件不存在: $config_file"
        return 1
    fi

    local start_time=$(date '+%H:%M:%S')
    print_info "=================================================="
    print_info "开始运行: ${character_name} (${character})"
    print_info "配置文件: $config_file"
    if [ -n "$emulator" ]; then
        print_info "模拟器: $emulator"
    fi
    if [ ${#env_overrides[@]} -gt 0 ]; then
        print_info "环境变量覆盖: ${env_overrides[*]}"
    fi
    print_info "开始时间: $start_time"
    print_info "=================================================="

    # 重试循环
    while [ $retry_count -lt $max_retries ]; do
        local cmd="uv run auto_dungeon.py -c \"$config_file\""
        if [ -n "$emulator" ]; then
            cmd="$cmd --emulator \"$emulator\""
        fi

        # 添加环境变量覆盖参数
        for override in "${env_overrides[@]}"; do
            cmd="$cmd -e \"$override\""
        done

        if eval "$cmd"; then
            local end_time=$(date '+%H:%M:%S')
            print_success "${character_name} 副本运行完成！"
            print_info "结束时间: $end_time"
            return 0
        else
            ((retry_count++))
            local end_time=$(date '+%H:%M:%S')
            print_error "${character_name} 副本运行失败！(第 $retry_count/$max_retries 次失败)"
            print_info "结束时间: $end_time"

            if [ $retry_count -lt $max_retries ]; then
                local wait_time=$((retry_count * 10))  # 第1次失败等待10秒，第2次等待20秒
                print_warning "⏳ 等待 ${wait_time} 秒后重新运行..."
                sleep $wait_time
                print_info "🔄 开始第 $((retry_count + 1)) 次重试..."
            fi
        fi
    done

    # 所有重试都失败了
    print_error "${character_name} 副本在 $max_retries 次重试后仍然失败！"
    return 1
}

# 显示帮助信息
show_help() {
    cat << EOF
${BLUE}自动化副本运行脚本${NC}

使用方法:
  ./run_all_dungeons.sh [选项] [角色名称...]

选项:
  -h, --help              显示此帮助信息
  -l, --list              列出所有可用的角色
  -a, --all               运行所有角色（默认行为）
  -i, --interactive       交互式选择角色
  -n, --no-prompt         失败时自动继续，不询问
  --emulator EMULATOR     指定模拟器（如：emulator-5554）
  -e, --env KEY=VALUE     环境变量覆盖（可多次使用）

角色名称:
  warrior             战士
  paladin             圣骑士
  mage                法师
  rogue               盗贼
  hunter              猎人
  warlock             术士
  druid               德鲁伊

重试机制:
  • 每个角色最多重试 3 次
  • 第 1 次失败后等待 10 秒重试
  • 第 2 次失败后等待 20 秒重试
  • 第 3 次失败后等待 30 秒重试
  • 所有重试都失败后才会继续下一个角色

示例:
  ./run_all_dungeons.sh                           # 运行所有角色（失败自动重试）
  ./run_all_dungeons.sh -n                        # 运行所有角色（失败自动重试，无提示）
  ./run_all_dungeons.sh warrior                   # 只运行战士
  ./run_all_dungeons.sh warrior mage              # 运行战士和法师
  ./run_all_dungeons.sh -i                        # 交互式选择
  ./run_all_dungeons.sh -l                        # 列出所有角色
  ./run_all_dungeons.sh --emulator emulator-5554  # 在指定模拟器上运行所有角色
  ./run_all_dungeons.sh mage --emulator emulator-5554  # 在指定模拟器上运行法师
  ./run_all_dungeons.sh -e enable_daily_collect=false  # 禁用每日收集
  ./run_all_dungeons.sh warrior -e enable_daily_collect=false -e enable_quick_afk=true  # 运行战士并覆盖配置

EOF
}

# 列出所有可用角色
list_characters() {
    print_info "可用的角色配置:"
    echo ""
    for character in "${CHARACTERS[@]}"; do
        local character_name=${CHARACTER_NAMES[$character]:-$character}
        local config_file="configs/${character}.json"
        if [ -f "$config_file" ]; then
            echo "  ✓ ${character_name} (${character})"
        else
            echo "  ✗ ${character_name} (${character}) - 配置文件不存在"
        fi
    done
    echo ""
}

# 交互式选择角色
interactive_select() {
    print_info "请选择要运行的角色:"
    echo ""

    local i=1
    for character in "${CHARACTERS[@]}"; do
        local character_name=${CHARACTER_NAMES[$character]:-$character}
        echo "  [$i] ${character_name} (${character})"
        ((i++))
    done
    echo "  [0] 运行所有角色"
    echo ""

    read -p "请输入数字选择 (0-${#CHARACTERS[@]}): " choice

    if [ "$choice" = "0" ]; then
        return 0
    elif [ "$choice" -ge 1 ] && [ "$choice" -le "${#CHARACTERS[@]}" ]; then
        local selected_character=${CHARACTERS[$choice]}
        SELECTED_CHARACTERS=("$selected_character")
        return 0
    else
        print_error "无效的选择"
        return 1
    fi
}

# 主函数
main() {
    local run_all=true
    local interactive=false
    local no_prompt=false
    local emulator=""
    local env_overrides=()
    SELECTED_CHARACTERS=()

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -l|--list)
                list_characters
                exit 0
                ;;
            -a|--all)
                run_all=true
                shift
                ;;
            -i|--interactive)
                interactive=true
                shift
                ;;
            -n|--no-prompt)
                no_prompt=true
                shift
                ;;
            --emulator)
                emulator="$2"
                shift 2
                ;;
            -e|--env)
                env_overrides+=("$2")
                shift 2
                ;;
            -*)
                print_error "未知选项: $1"
                echo "使用 -h 或 --help 查看帮助信息"
                exit 1
                ;;
            *)
                run_all=false
                SELECTED_CHARACTERS+=("$1")
                shift
                ;;
        esac
    done

    # 交互式选择
    if [ "$interactive" = true ]; then
        interactive_select || exit 1
        if [ ${#SELECTED_CHARACTERS[@]} -eq 0 ]; then
            run_all=true
        else
            run_all=false
        fi
    fi

    # 确定要运行的角色列表
    if [ "$run_all" = true ]; then
        SELECTED_CHARACTERS=("${CHARACTERS[@]}")
        print_info "将依次运行所有角色的副本"
    else
        print_info "将运行选定的 ${#SELECTED_CHARACTERS[@]} 个角色"
    fi

    echo ""

    # 统计信息
    local total=${#SELECTED_CHARACTERS[@]}
    local success=0
    local failed=0
    local start_time=$(date +%s)

    print_info "准备运行 ${total} 个角色: ${SELECTED_CHARACTERS[*]}"

    # 依次运行每个角色
    for character in "${SELECTED_CHARACTERS[@]}"; do
        echo ""
        print_info "正在运行第 $((success + failed + 1))/${total} 个角色..."

        if run_character "$character" "$emulator" "${env_overrides[@]}"; then
            ((success++))
            print_success "成功完成！继续下一个角色..."
        else
            ((failed++))
            print_error "运行失败（已重试 3 次）！"
            print_warning "继续运行下一个角色..."
        fi
        echo ""
    done

    # 计算总耗时
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local hours=$((duration / 3600))
    local minutes=$(((duration % 3600) / 60))
    local seconds=$((duration % 60))

    # 打印总结
    echo ""
    print_info "=================================================="
    print_info "运行总结"
    print_info "=================================================="
    print_info "总共运行: ${total} 个角色"
    print_success "成功: ${success} 个"
    if [ $failed -gt 0 ]; then
        print_error "失败: ${failed} 个"
    fi
    print_info "总耗时: ${hours}小时 ${minutes}分钟 ${seconds}秒"
    print_info "=================================================="
    echo ""

    if [ $failed -gt 0 ]; then
        exit 1
    fi
}

# 运行主函数
main "$@"
