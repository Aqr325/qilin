#!/usr/bin/env node
/**
 * 麒麟OS Agent 发布脚本
 *
 * 用法:
 *   node scripts/publish-release.js [patch|minor|major]
 *   node scripts/publish-release.js --version=2.2.0
 *
 * 功能:
 *   1. 版本号自增（patch/minor/major 或指定版本）
 *   2. 更新 package.json 版本
 *   3. 构建 installer（electron-builder）
 *   4. 创建 GitHub Release 并上传安装包
 *   5. 自动生成更新日志（latest.yml / latest-mac.yml）
 *
 * 前置条件:
 *   - GitHub CLI (gh) 已安装并登录
 *   - GitHub 仓库 HONOR/kylin-secops-desktop 已存在
 *   - 仓库已有推送权限
 */

const { execSync } = require('child_process')
const path = require('path')
const fs = require('fs')

const ROOT = path.resolve(__dirname, '..')
const PACKAGE_JSON = path.join(ROOT, 'package.json')
const RELEASE_DIR = path.join(ROOT, 'release')

// ─── 解析参数 ───
const args = process.argv.slice(2)
let bumpType = 'patch' // default
let customVersion = null

for (const arg of args) {
  if (arg.startsWith('--version=')) {
    customVersion = arg.split('=')[1]
  } else if (['patch', 'minor', 'major'].includes(arg)) {
    bumpType = arg
  }
}

// ─── 彩色输出 ───
const colors = {
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  cyan: (s) => `\x1b[36m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  red: (s) => `\x1b[31m${s}\x1b[0m`,
}

function step(msg) { console.log(`\n${colors.cyan('▶')} ${msg}`) }
function ok(msg) { console.log(`  ${colors.green('✓')} ${msg}`) }
function warn(msg) { console.log(`  ${colors.yellow('!')} ${msg}`) }

// ─── 1. 版本自增 ───
step('更新版本号...')

const pkg = JSON.parse(fs.readFileSync(PACKAGE_JSON, 'utf-8'))
const currentVersion = pkg.version
const [major, minor, patch] = currentVersion.split('.').map(Number)

let newVersion
if (customVersion) {
  newVersion = customVersion
} else if (bumpType === 'major') {
  newVersion = `${major + 1}.0.0`
} else if (bumpType === 'minor') {
  newVersion = `${major}.${minor + 1}.0`
} else {
  newVersion = `${major}.${minor}.${patch + 1}`
}

console.log(`  ${currentVersion} → ${colors.green(newVersion)}`)

// ─── 2. 确认 ───
console.log(`\n  即将发布 ${colors.cyan(`v${newVersion}`)} 到 GitHub Releases`)
console.log('  按 Enter 继续, Ctrl+C 取消')
execSync('read', { stdio: 'inherit' })

// ─── 3. 更新 package.json ───
pkg.version = newVersion
fs.writeFileSync(PACKAGE_JSON, JSON.stringify(pkg, null, 2) + '\n')
ok(`package.json 版本更新为 ${newVersion}`)

// ─── 4. 构建 ───
step('构建安装包...')
execSync('npm run build', { cwd: ROOT, stdio: 'inherit' })
ok('构建完成')

// ─── 5. 更新 latest.yml ───
// electron-updater 使用 latest.yml 来检测更新
// electron-builder 构建时已自动生成

// ─── 6. 创建 GitHub Release ───
step('创建 GitHub Release...')

// 收集构建产物
const installerName = `麒麟OS安全运维Agent-Setup-${newVersion}.exe`
const installerPath = path.join(RELEASE_DIR, installerName)
const ymlPath = path.join(RELEASE_DIR, 'latest.yml')

if (!fs.existsSync(installerPath)) {
  throw new Error(`安装包未找到: ${installerPath}\n构建产物: ${fs.readdirSync(RELEASE_DIR).join(', ')}`)
}

// 使用 gh CLI 创建 release
try {
  // 检查 gh 是否登录
  execSync('gh auth status', { stdio: 'pipe' })

  // 创建 release
  const tagName = `v${newVersion}`
  execSync(
    `gh release create ${tagName} "${installerPath}" "${ymlPath}" ` +
    `--repo HONOR/kylin-secops-desktop ` +
    `--title "麒麟OS安全运维 v${newVersion}" ` +
    `--notes "## 麒麟OS安全运维 Agent v${newVersion}\\n\\n请下载安装包并运行以更新。"`,
    { cwd: ROOT, stdio: 'inherit' }
  )
  ok(`GitHub Release v${newVersion} 创建成功`)
} catch (err) {
  warn(`GitHub Release 创建失败: ${err.message}`)
  warn('请手动创建 Release:')
  warn(`  1. 上传 ${installerPath}`)
  warn(`  2. 上传 ${ymlPath}`)
  warn(`  3. Tag: v${newVersion}`)
}

// ─── 7. 提交并推送版本变更 ───
step('提交版本变更...')
try {
  execSync('git add package.json release/latest.yml', { cwd: ROOT, stdio: 'pipe' })
  execSync(`git commit -m "chore: bump version to ${newVersion}"`, { cwd: ROOT, stdio: 'pipe' })
  execSync('git push', { cwd: ROOT, stdio: 'pipe' })
  ok('版本变更已推送')
} catch (err) {
  warn(`Git 操作失败: ${err.message}`)
  warn('请手动提交: git add . && git commit -m "bump version" && git push')
}

console.log(`\n${colors.green('══════════════════════════════════════')}`)
console.log(` 发布完成! v${currentVersion} → ${colors.green(`v${newVersion}`)}`)
console.log(`${colors.green('══════════════════════════════════════')}\n`)
