# Pulse Bot Pre-commit Hook

## 作用

当 bot 的 commit 试图写入 `00_Inbox/_pulse/` 以外的路径时，该 hook 终止 commit 并报错。

## 安装

将 hook 复制到 vault 仓库的 `.git/hooks/` 目录并设为可执行：

```bash
# 在 vault 仓库根目录执行
cp /path/to/pulse-bot/docs/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## 工作原理

Hook 通过 `git config user.name` 识别 bot 提交（值为 "Pulse Bot"）。
若是 bot 提交，检查 `git diff --cached --name-only` 中所有文件路径。
所有文件必须以 `00_Inbox/_pulse/` 开头，否则 commit 被终止。

## 卸载

```bash
rm .git/hooks/pre-commit
```

## 测试

```bash
# 在 vault 仓库中：
# 1. 模拟 bot 写入 _pulse/ 内文件 — 应通过
git config user.name "Pulse Bot"
echo "test" > "00_Inbox/_pulse/test.md"
git add "00_Inbox/_pulse/test.md"
git commit -m "test pulse"  # 应成功
git reset HEAD~1

# 2. 模拟 bot 写入 _pulse/ 外文件 — 应被拦截
echo "test" > "Other_Folder/test.md"
git add "Other_Folder/test.md"
git commit -m "test blocked"  # 应失败
rm "Other_Folder/test.md"
git checkout -- .
```
