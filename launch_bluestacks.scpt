#!/usr/bin/env osascript

-- 启动 BlueStacks Air 多开管理器
tell application "BlueStacksMIM"
    activate
end tell

-- 等待应用启动
delay 2

-- 点击左上角的"全选"复选框 (坐标约为 30, 82)
tell application "System Events"
    click at {30, 82}
end tell

-- 等待一下
delay 1

-- 点击"开始"按钮 (坐标约为 629, 148)
tell application "System Events"
    click at {629, 148}
end tell

-- 完成
display notification "BlueStacks 已执行全选和开始操作" with title "完成"

