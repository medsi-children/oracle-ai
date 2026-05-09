import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';

const projectDir = '/Users/ori.space.cat/Сушкевич Бот/oracle-ai';
const envFile = `${projectDir}/.env`;
const docker = '/usr/local/bin/docker';
const cloudflared = '/opt/homebrew/bin/cloudflared';
const logFile = '/private/tmp/oracle-ai-shop-tunnel-manager.log';
const cloudflaredLogFile = '/private/tmp/oracle-ai-shop-cloudflared.log';

function append(file, message) {
  fs.appendFileSync(file, message);
}

function log(message) {
  append(logFile, `${new Date().toISOString()} ${message}\n`);
}

function run(command, args, options = {}) {
  log(`$ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? projectDir,
    encoding: 'utf8',
    timeout: options.timeout ?? 30000,
    env: {
      ...process.env,
      PATH: '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
    },
  });

  if (result.stdout) append(logFile, result.stdout);
  if (result.stderr) append(logFile, result.stderr);
  if (result.error) log(`Command error: ${result.error.message}`);
  return result.status === 0;
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForBackend() {
  for (let attempt = 1; attempt <= 60; attempt += 1) {
    if (run('/usr/bin/curl', ['-sS', '--max-time', '5', 'http://localhost:8000/health'], { timeout: 8000 })) {
      log('Backend is ready');
      return true;
    }
    log(`Waiting for backend (${attempt}/60)`);
    await sleep(2000);
  }

  return false;
}

function updatePublicWebappUrl(url) {
  const env = fs.readFileSync(envFile, 'utf8');
  const next = env.replace(
    /^PUBLIC_WEBAPP_URL=.*$/m,
    `PUBLIC_WEBAPP_URL=${url}/app/shop`,
  );

  if (next === env) {
    throw new Error('PUBLIC_WEBAPP_URL line not found in .env');
  }

  fs.writeFileSync(envFile, next);
  log(`PUBLIC_WEBAPP_URL updated: ${url}/app/shop`);
  run(docker, ['compose', 'up', '-d', '--force-recreate', 'api'], { cwd: projectDir, timeout: 60000 });
}

async function main() {
  fs.writeFileSync(logFile, '');
  fs.writeFileSync(cloudflaredLogFile, '');
  log('Shop tunnel manager starting');

  const backendReady = await waitForBackend();
  if (!backendReady) process.exit(1);

  const tunnel = spawn(cloudflared, ['tunnel', '--url', 'http://localhost:8000'], {
    cwd: projectDir,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PATH: '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
    },
  });

  let urlSeen = false;
  const handleOutput = (buffer) => {
    const text = buffer.toString();
    append(cloudflaredLogFile, text);
    const match = text.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/);
    if (match && !urlSeen) {
      urlSeen = true;
      updatePublicWebappUrl(match[0]);
    }
  };

  tunnel.stdout.on('data', handleOutput);
  tunnel.stderr.on('data', handleOutput);

  const shutdown = () => {
    log('Shop tunnel manager stopping');
    tunnel.kill('SIGTERM');
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  tunnel.on('exit', (code, signal) => {
    log(`cloudflared exited: code=${code} signal=${signal}`);
    process.exit(code ?? 1);
  });
}

main().catch((error) => {
  log(`Fatal: ${error.stack || error.message}`);
  process.exit(1);
});
