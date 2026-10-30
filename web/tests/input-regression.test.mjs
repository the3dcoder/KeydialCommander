import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const root = fileURLToPath(new URL('..', import.meta.url))
let server, browser, browserDir, socket, nextId = 0
const pending = new Map()
const browserErrors = []

async function until(check, label, timeout = 10000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    try {
      const value = await check()
      if (value) return value
    } catch (error) {
      if (!/Execution context|Cannot find context|Inspected target navigated/.test(error.message)) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, 30))
  }
  throw new Error(`Timed out: ${label}`)
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result.value
}
async function click(expression) {
  await evaluate(`(${expression}).click()`)
}
const capture = 'document.querySelector(".capture")'
async function focusCapture() {
  await evaluate(`${capture}.blur()`)
  const point = await center(capture)
  await move('mousePressed', point, { button: 'left', buttons: 1, clickCount: 1 })
  await move('mouseReleased', point, { button: 'left', buttons: 0, clickCount: 1 })
  await until(() => evaluate(`${capture}.style.outline.includes('solid')`), 'capture focused')
}
async function key(type, code, flags = {}) {
  await evaluate(`${capture}.dispatchEvent(new KeyboardEvent(${JSON.stringify(type)}, ${JSON.stringify({ code, bubbles: true, cancelable: true, ...flags })}))`)
}
async function text() {
  return evaluate(`${capture}.textContent`)
}
async function reset(select = true) {
  const previousPage = await evaluate('window.__pageId')
  await send('Page.reload')
  await until(() => evaluate(`window.__pageId !== ${JSON.stringify(previousPage)} && !!document.querySelector("button[title=BUTTON_1]") && [...document.querySelectorAll(".profiles button")].some(e => e.textContent.trim() === "B")`), 'app ready')
  if (!select) return
  await click('document.querySelector("button[title=BUTTON_1]")')
  await until(() => evaluate('!!document.querySelector(".capture") && document.querySelector(".insp h3")?.textContent.includes("BUTTON_1")'), 'inspector ready')
}
async function card(label) {
  return `[...document.querySelectorAll('.libcard')].find(e => e.textContent.includes(${JSON.stringify(label)}))`
}
async function move(type, point, extra = {}) {
  await send('Input.dispatchMouseEvent', { type, ...point, ...extra })
}
async function center(expression) {
  return evaluate(`(() => { const e = ${expression}; e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`)
}
async function drag(label, actionId) {
  const from = await center(await card(label))
  const to = await center(`document.querySelector('button[title=${actionId}]')`)
  await move('mouseMoved', from)
  await move('mousePressed', from, { button: 'left', buttons: 1, clickCount: 1 })
  await move('mouseMoved', { x: from.x + 8, y: from.y }, { button: 'left', buttons: 1 })
  await until(() => evaluate(`!!document.querySelector('.libcard[style*="grabbing"]')`), 'drag activated')
  for (let step = 1; step <= 8; step++) {
    await move('mouseMoved', { x: from.x + (to.x - from.x) * step / 8, y: from.y + (to.y - from.y) * step / 8 }, { button: 'left', buttons: 1 })
  }
  try {
    await until(() => evaluate(`document.querySelector('button[title=${actionId}]').classList.contains('over')`), 'drop target reached')
  } catch (error) {
    const over = await evaluate('[...document.querySelectorAll(".over")].map(e => e.title)')
    throw new Error(`${error.message}; pointer=${JSON.stringify(to)}, active targets=${JSON.stringify(over)}`)
  }
  await move('mouseReleased', to, { button: 'left', buttons: 0, clickCount: 1 })
}

before(async () => {
  server = await createServer({ root, server: { host: '127.0.0.1', port: 0, proxy: {} }, configFile: false, plugins: [(await import('@vitejs/plugin-react')).default()] })
  await server.listen()
  const address = server.httpServer.address()
  const browserPath = process.env.KEYDIAL_TEST_BROWSER || [
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  ].find(existsSync)
  assert.ok(browserPath, 'Set KEYDIAL_TEST_BROWSER to a Chromium executable')
  browserDir = await mkdtemp(join(tmpdir(), 'commander-input-browser-'))
  browser = spawn(browserPath, ['--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${browserDir}`, 'about:blank'], { stdio: 'ignore' })
  const port = await until(async () => {
    try { return (await readFile(join(browserDir, 'DevToolsActivePort'), 'utf8')).split('\n')[0] } catch { return null }
  }, 'browser debugger')
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
  socket = new WebSocket(targets.find((target) => target.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if (message.id) {
      const call = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) call.reject(new Error(message.error.message))
      else call.resolve(message.result)
    } else if (message.method === 'Runtime.exceptionThrown') browserErrors.push(message.params.exceptionDetails.text)
  }
  await send('Runtime.enable')
  await send('Page.enable')
  await send('Emulation.setFocusEmulationEnabled', { enabled: true })
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.__pageId = Math.random();
    window.__api = { active: 'A', writes: [], bindingReads: 0, bindings: { A: {}, B: {} } };
    window.confirm = () => true;
    const NativeWebSocket = window.WebSocket;
    window.WebSocket = class extends NativeWebSocket {
      constructor(url, ...args) {
        if (String(url).endsWith('/api/events')) return window.__eventSocket = { close() {} };
        super(url, ...args);
      }
    };
    window.fetch = async (input, options = {}) => {
      const path = String(input), method = options.method || 'GET', state = window.__api;
      let body = {};
      if (method !== 'GET') {
        const value = options.body ? JSON.parse(options.body) : null;
        state.writes.push({ path, method, body: value });
        const match = /^\\/api\\/profiles\\/([^/]+)\\/bindings\\/(.+)$/.exec(path);
        if (match && method === 'PUT') {
          if (state.holdSave) await new Promise(resolve => state.releaseSave = resolve);
          state.bindings[match[1]][match[2]] = value;
        }
        if (path.endsWith('/activate')) state.active = path.split('/')[3];
      }
      if (path === '/api/status') body = { device: { connected: false }, service: { version: 'test' }, active_profile: state.active };
      else if (path === '/api/profiles') body = ['A', 'B'].map(name => ({name, binding_count: Object.keys(state.bindings[name]).length, active: name === state.active}));
      else if (path === '/api/keys') body = { groups: { letters: ['KEY_C', 'KEY_K'] }, all: ['KEY_C', 'KEY_K'] };
      else if (path.endsWith('/bindings')) {
        state.bindingReads++;
        if (state.holdBindings) await new Promise(resolve => state.releaseBindings = resolve);
        body = { bindings: state.bindings[path.split('/')[3]], dial_sensitivity: 1 };
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
  ` })
  await send('Page.navigate', { url: `http://127.0.0.1:${address.port}` })
  await until(() => evaluate('!!document.querySelector(".app")'), 'first render')
})
after(async () => {
  socket?.close()
  if (browser && browser.exitCode === null) {
    browser.kill('SIGTERM')
    await new Promise((resolve) => browser.once('exit', resolve))
  }
  await server?.close()
  if (browserDir) await rm(browserDir, { recursive: true, force: true })
})

test('Ctrl+C waits for the primary key', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'ControlLeft', { ctrlKey: true })
  await key('keydown', 'KeyC', { ctrlKey: true })
  assert.equal(await text(), 'LEFTCTRL + C')
})

test('multiple modifiers retain their side and wait for the primary key', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'ControlRight', { ctrlKey: true })
  await key('keydown', 'ShiftLeft', { ctrlKey: true, shiftKey: true })
  await key('keydown', 'KeyC', { ctrlKey: true, shiftKey: true })
  assert.equal(await text(), 'RIGHTCTRL + LEFTSHIFT + C')
})

test('a standalone modifier commits on release and repeated keydowns are ignored', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'AltRight', { altKey: true })
  await key('keydown', 'AltRight', { altKey: true, repeat: true })
  assert.equal(await text(), 'Press a shortcut…')
  await key('keyup', 'AltRight')
  assert.equal(await text(), 'RIGHTALT')
})

test('blur and a new capture discard pending modifiers', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'ControlLeft', { ctrlKey: true })
  await focusCapture()
  await key('keydown', 'KeyK')
  assert.equal(await text(), 'K')
  await focusCapture()
  await key('keydown', 'KeyC', { repeat: true })
  assert.equal(await text(), 'K')
  await key('keydown', 'KeyC')
  assert.equal(await text(), 'C')
})

test('dropping an unfinished template stages a draft without sending it', async () => {
  await reset()
  await drag('Launch app', 'BUTTON_2')
  await until(() => evaluate('document.querySelector(".insp h3")?.textContent.includes("BUTTON_2")'), 'drop selection')
  assert.deepEqual(await evaluate('window.__api.writes'), [])
  assert.equal(await evaluate('document.querySelector(".insp select").value'), 'command')
  assert.equal(await evaluate('document.querySelector(".insp input").value'), '')
})

test('clicking a template edits the selected control and only Save writes the configured draft', async () => {
  await reset()
  await click(await card('Keystroke'))
  await focusCapture()
  await key('keydown', 'KeyK')
  assert.deepEqual(await evaluate('window.__api.writes'), [])
  await click('[...document.querySelectorAll(".insp button")].find(e => e.textContent === "Save")')
  await until(() => evaluate('window.__api.writes.length === 1'), 'saved binding')
  assert.deepEqual(await evaluate('window.__api.writes'), [{ path: '/api/profiles/A/bindings/BUTTON_1', method: 'PUT', body: { type: 'keystroke', keys: ['KEY_K'] } }])
})

test('clicking a different library template replaces the current unsaved draft', async () => {
  await reset()
  await click(await card('Launch app'))
  await until(() => evaluate('document.querySelector(".insp select").value === "command"'), 'clicked command draft')
  assert.equal(await evaluate('document.querySelector(".insp input").value'), '')
  await click(await card('Macro'))
  await until(() => evaluate('document.querySelector(".insp select").value === "macro"'), 'clicked macro draft')
  assert.deepEqual(await evaluate('window.__api.writes'), [])
})

test('switching between unbound profiles discards the previous profile draft', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'KeyK')
  assert.equal(await text(), 'K')
  await click('[...document.querySelectorAll(".profiles button")].find(e => e.textContent.trim() === "B")')
  await until(() => evaluate('window.__api.active === "B"'), 'profile activated')
  await until(async () => (await text()) !== 'K', 'profile draft reset')
  await click('[...document.querySelectorAll(".insp button")].find(e => e.textContent === "Save")')
  const writes = await evaluate('window.__api.writes.filter(e => e.method === "PUT")')
  assert.equal(writes.length, 1)
  assert.equal(writes[0].path, '/api/profiles/B/bindings/BUTTON_1')
  assert.deepEqual(writes[0].body.keys, [])
  assert.deepEqual(browserErrors, [])
})


test('changing the selected control discards its unsaved template draft', async () => {
  await reset()
  await click(await card('Launch app'))
  await until(() => evaluate('document.querySelector(".insp select").value === "command"'), 'template draft')
  await click('document.querySelector("button[title=BUTTON_2]")')
  await until(() => evaluate('!!document.querySelector(".capture")'), 'new control editor')
  assert.equal(await text(), 'Click to capture')
  assert.deepEqual(await evaluate('window.__api.writes'), [])
})

test('a template click without a selected control leaves bindings unchanged', async () => {
  await reset(false)
  await click(await card('Launch app'))
  assert.equal(await evaluate('document.querySelector(".insp select")'), null)
  assert.deepEqual(await evaluate('window.__api.writes'), [])
})


test('a remote profile change resets an in-progress modifier capture', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'ControlLeft', { ctrlKey: true })
  await evaluate(`window.__api.active = 'B'; window.__eventSocket.onmessage({data: JSON.stringify({type: 'profile_changed', name: 'B'})})`)
  await until(() => evaluate('[...document.querySelectorAll(".profiles button")].some(e => e.textContent.trim() === "B" && e.classList.contains("active"))'), 'remote profile change')
  await key('keyup', 'ControlLeft')
  assert.equal(await text(), 'Click to capture')
})

test('window focus loss cancels a pending modifier without committing it', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'ControlLeft', { ctrlKey: true })
  await evaluate('window.dispatchEvent(new Event("blur"))')
  await key('keyup', 'ControlLeft')
  assert.equal(await text(), 'Click to capture')
  await focusCapture()
  await key('keydown', 'KeyK')
  assert.equal(await text(), 'K')
})


test('a saved draft waits for refreshed bindings and then yields to remote updates', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'KeyK')
  await evaluate('window.__api.holdBindings = true')
  await click('[...document.querySelectorAll(".insp button")].find(e => e.textContent === "Save")')
  await until(() => evaluate('typeof window.__api.releaseBindings === "function"'), 'save refetch pending')
  assert.equal(await text(), 'K')
  await evaluate('window.__api.holdBindings = false; window.__api.releaseBindings()')
  await until(() => evaluate('document.querySelector("button[title=BUTTON_1] .klabel").textContent === "K"'), 'saved binding refreshed')
  await evaluate(`window.__api.bindings.A.BUTTON_1 = {type: 'keystroke', keys: ['KEY_C']}; window.__eventSocket.onmessage({data: JSON.stringify({type: 'bindings_changed', profile: 'A'})})`)
  await until(() => evaluate('document.querySelector("button[title=BUTTON_1] .klabel").textContent === "C"'), 'remote binding refreshed')
  assert.equal(await text(), 'C')
})

test('edits made while Save is pending remain an unsaved draft after it completes', async () => {
  await reset()
  await focusCapture()
  await key('keydown', 'KeyK')
  await evaluate('window.__api.holdSave = true')
  await click('[...document.querySelectorAll(".insp button")].find(e => e.textContent === "Save")')
  await until(() => evaluate('typeof window.__api.releaseSave === "function"'), 'save request pending')
  await focusCapture()
  await key('keydown', 'KeyC')
  await evaluate('window.__api.releaseSave()')
  await until(() => evaluate('document.querySelector("button[title=BUTTON_1] .klabel").textContent === "K"'), 'original save completed')
  assert.equal(await text(), 'C')
  assert.deepEqual(await evaluate('window.__api.bindings.A.BUTTON_1.keys'), ['KEY_K'])
  await evaluate(`window.__api.bindings.A.BUTTON_1 = {type: 'keystroke', keys: ['KEY_J']}; window.__eventSocket.onmessage({data: JSON.stringify({type: 'bindings_changed', profile: 'A'})})`)
  await until(() => evaluate('document.querySelector("button[title=BUTTON_1] .klabel").textContent === "J"'), 'subsequent remote binding refreshed')
  assert.equal(await text(), 'C')
})
