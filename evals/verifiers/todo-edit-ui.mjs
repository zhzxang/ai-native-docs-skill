#!/usr/bin/env node
// Exercise submitted App.tsx in a browser with a trusted server and assertion code.
// Dependencies come from the frozen controller copy, never project vite.config/tests.
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, realpathSync, rmSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const checks = []
let currentCheck = 'prepare trusted UI harness'
let server, browser, scratch
const infra = (message) => Object.assign(new Error(message), { infrastructure: true })
async function check(name, fn) {
  currentCheck = name
  await fn()
  checks.push({ name, passed: true })
}

async function main() {
  const project = process.argv[2]
  if (!project || !path.isAbsolute(project)) throw infra('Expected absolute project path')
  const dependencyPath = process.env.EVAL_TODO_NODE_MODULES
  if (!dependencyPath || !path.isAbsolute(dependencyPath) || !existsSync(dependencyPath)) {
    throw infra('Set EVAL_TODO_NODE_MODULES to the trusted frozen Vite/React node_modules directory')
  }
  const dependencyRoot = realpathSync(dependencyPath)
  if (dependencyRoot === realpathSync(project) || dependencyRoot.startsWith(realpathSync(project) + path.sep)) {
    throw infra('EVAL_TODO_NODE_MODULES must be outside the submitted project')
  }
  const playwrightPackage = process.env.EVAL_PLAYWRIGHT_MODULE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
  const require = createRequire(import.meta.url)
  let chromium, createServer
  try {
    ;({ chromium } = require(playwrightPackage))
    ;({ createServer } = await import(pathToFileURL(path.join(dependencyRoot, 'vite/dist/node/index.js')).href))
  } catch (error) {
    throw infra(`Missing trusted browser/server dependencies: ${error.message}. Configure EVAL_PLAYWRIGHT_MODULE and EVAL_TODO_NODE_MODULES.`)
  }
  scratch = mkdtempSync(path.join(os.tmpdir(), 'todo-eval-ui-'))
  const aliases = {
    'react': path.join(dependencyRoot, 'react/index.js'),
    'react/jsx-runtime': path.join(dependencyRoot, 'react/jsx-runtime.js'),
    'react/jsx-dev-runtime': path.join(dependencyRoot, 'react/jsx-dev-runtime.js'),
    'react-dom/client': path.join(dependencyRoot, 'react-dom/client.js'),
    'react-dom': path.join(dependencyRoot, 'react-dom/index.js'),
  }
  // Exact regular expressions prevent the react alias swallowing react/jsx-runtime.
  const alias = Object.entries(aliases).map(([find, replacement]) => ({ find: new RegExp('^' + find.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'), replacement }))
  try {
    server = await createServer({
      configFile: false,
      envFile: false,
      root: project,
      cacheDir: path.join(scratch, 'vite-cache'),
      logLevel: 'silent',
      resolve: { alias },
      optimizeDeps: { noDiscovery: true, include: Object.keys(aliases) },
      server: { host: '127.0.0.1', port: 0, fs: { allow: [project, dependencyRoot, scratch] } },
      plugins: [{
        name: 'trusted-todo-eval-entry',
        configureServer(vite) {
          vite.middlewares.use(async (request, response, next) => {
            if (request.url !== '/__eval_todo__') return next()
            try {
              const html = await vite.transformIndexHtml('/__eval_todo__', '<!doctype html><html><head><meta charset="utf-8"></head><body><div id="root"></div><script type="module">import React from "react"; import {createRoot} from "react-dom/client"; import App from "/src/App.tsx"; createRoot(document.getElementById("root")).render(React.createElement(App));</script></body></html>')
              response.setHeader('Content-Type', 'text/html; charset=utf-8')
              response.end(html)
            } catch (error) { response.statusCode = 500; response.end(error.message) }
          })
        },
      }],
    })
    await server.listen()
  } catch (error) { throw infra(`Could not start trusted local Vite server: ${error.message}`) }
  const installedChrome = process.platform === 'darwin' ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : undefined
  const executablePath = process.env.EVAL_BROWSER_EXECUTABLE || (installedChrome && existsSync(installedChrome) ? installedChrome : undefined)
  try {
    browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
  } catch (error) { throw infra(`Could not launch browser: ${error.message}. Configure EVAL_BROWSER_EXECUTABLE or install the browser separately.`) }
  const page = await browser.newPage()
  page.setDefaultTimeout(8000)
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  const seed = [
    { id: 'ui-one', text: '第一件原始待办', completed: false },
    { id: 'ui-two', text: '第二件已完成待办', completed: true },
    { id: 'ui-three', text: '第三件保留待办', completed: false },
  ]
  await page.addInitScript((items) => {
    if (!localStorage.getItem('vite-todo.items.v1')) localStorage.setItem('vite-todo.items.v1', JSON.stringify(items))
  }, seed)
  const address = server.httpServer.address()
  const url = `http://127.0.0.1:${address.port}/__eval_todo__`
  const rows = page.locator('li')
  const row = (title) => rows.filter({ hasText: title })
  const stored = () => page.evaluate(() => JSON.parse(localStorage.getItem('vite-todo.items.v1')))
  const waitStored = async (expected) => {
    await page.waitForFunction((items) => {
      const actual = JSON.parse(localStorage.getItem('vite-todo.items.v1') || 'null')
      return Array.isArray(actual) && actual.length === items.length && actual.every((item, index) =>
        item.id === items[index].id && item.text === items[index].text && item.completed === items[index].completed)
    }, expected)
    assert.deepEqual(await stored(), expected)
  }
  const edit = async (title) => {
    // Editing replaces the visible title with an input; keep the row's position
    // rather than filtering again by text that disappears from the DOM.
    const index = await row(title).evaluate((element) => Array.from(element.parentElement.children).indexOf(element))
    const item = rows.nth(index)
    await item.getByRole('button', { name: /^编辑(?:[：:].*)?$/ }).click()
    const input = item.getByRole('textbox', { name: '编辑待办内容', exact: true })
    await input.waitFor({ state: 'visible' })
    assert.equal(await input.inputValue(), title)
    return { item, input }
  }
  await check('App loads original rows without runtime errors', async () => {
    await page.goto(url)
    await row(seed[0].text).waitFor({ state: 'visible' })
    assert.equal(await rows.count(), 3)
    assert.deepEqual(pageErrors, [])
  })
  let expected = seed.map((item) => ({ ...item }))
  await check('edit Save trims the title and preserves other rows and completion', async () => {
    const { item, input } = await edit(expected[0].text)
    await input.fill('  点击保存后的标题  ')
    await item.getByRole('button', { name: '保存', exact: true }).click()
    expected[0].text = '点击保存后的标题'
    await waitStored(expected)
    assert.equal(await row(expected[0].text).getByRole('checkbox').isChecked(), false)
    assert.equal(await row(expected[1].text).getByRole('checkbox').isChecked(), true)
  })
  await check('Cancel and Escape discard draft changes', async () => {
    let editor = await edit(expected[0].text)
    await editor.input.fill('取消后不能保存')
    await editor.item.getByRole('button', { name: '取消', exact: true }).click()
    await row(expected[0].text).waitFor({ state: 'visible' })
    assert.deepEqual(await stored(), expected)
    editor = await edit(expected[0].text)
    await editor.input.fill('Escape后不能保存')
    await editor.input.press('Escape')
    await row(expected[0].text).waitFor({ state: 'visible' })
    assert.deepEqual(await stored(), expected)
  })
  await check('Enter commits editing without creating an extra Todo', async () => {
    const { input } = await edit(expected[0].text)
    await input.fill('  Enter保存后的标题  ')
    await input.press('Enter')
    expected[0].text = 'Enter保存后的标题'
    await waitStored(expected)
    assert.equal(await rows.count(), 3)
  })
  await check('blank edits do not replace or delete an existing title', async () => {
    const { item, input } = await edit(expected[0].text)
    await input.fill('   ')
    await input.press('Enter')
    const save = item.getByRole('button', { name: '保存', exact: true })
    if (await save.count() && await save.isEnabled()) await save.click()
    assert.deepEqual(await stored(), expected)
    const cancel = item.getByRole('button', { name: '取消', exact: true })
    if (await cancel.count()) await cancel.click()
    await row(expected[0].text).waitFor({ state: 'visible' })
    assert.equal(await rows.count(), 3)
  })
  await check('completed items remain completed after editing and reload persists both titles', async () => {
    const { item, input } = await edit(expected[1].text)
    await input.fill('已完成项目的新标题')
    await item.getByRole('button', { name: '保存', exact: true }).click()
    expected[1].text = '已完成项目的新标题'
    await waitStored(expected)
    await page.reload()
    await row(expected[0].text).waitFor({ state: 'visible' })
    assert.equal(await row(expected[1].text).getByRole('checkbox').isChecked(), true)
    assert.equal(await rows.count(), 3)
    assert.deepEqual(await stored(), expected)
  })
  await check('existing toggle, filter, delete, clear and add controls still work', async () => {
    await row(expected[0].text).getByRole('checkbox').check()
    expected[0].completed = true
    await waitStored(expected)
    await page.getByRole('button', { name: '待完成', exact: true }).click()
    assert.equal(await rows.count(), 1)
    assert.equal(await row(expected[2].text).count(), 1)
    await page.getByRole('button', { name: '已完成', exact: true }).click()
    assert.equal(await rows.count(), 2)
    await page.getByRole('button', { name: '全部', exact: true }).click()
    await row(expected[0].text).getByRole('button', { name: /^删除/ }).click()
    expected = expected.slice(1)
    await waitStored(expected)
    await page.getByRole('button', { name: '清空已完成', exact: true }).click()
    expected = expected.filter((item) => !item.completed)
    await waitStored(expected)
    await page.getByRole('textbox', { name: '新待办内容', exact: true }).fill('  编辑后仍能新增  ')
    await page.getByRole('button', { name: '添加', exact: true }).click()
    await row('编辑后仍能新增').waitFor({ state: 'visible' })
    const final = await stored()
    assert.equal(final.length, 2)
    assert.deepEqual(final[0], expected[0])
    assert.equal(final[1].text, '编辑后仍能新增')
    assert.equal(final[1].completed, false)
    assert.equal(typeof final[1].id, 'string')
    assert.ok(final[1].id && final[1].id !== final[0].id)
    assert.deepEqual(pageErrors, [])
  })
  console.log(JSON.stringify({ status: 'passed', checks, marker: 'TODO_EDIT_UI_PASS' }))
}

try {
  await main()
} catch (error) {
  checks.push({ name: currentCheck, passed: false, detail: error.message })
  console.log(JSON.stringify({ status: error.infrastructure ? 'infrastructure_error' : 'failed', checks, error: error.message }))
  process.exitCode = error.infrastructure ? 2 : 1
} finally {
  if (browser) await browser.close().catch(() => {})
  if (server) await server.close().catch(() => {})
  if (scratch) rmSync(scratch, { recursive: true, force: true })
}
