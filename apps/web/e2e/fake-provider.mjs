// W10 E2E real — Fake provider OpenAI-compatible (local, NO internet).
// Responde a POST /v1/chat/completions con una respuesta válida de OpenAI.
// Se usa con el endpoint profile "local-ollama" (http://ollama.internal:11434/v1).
// El token esperado es el que el test siembra como BYOK (fake-ollama-key).
import http from 'node:http';

const PORT = Number(process.env.FAKE_PROVIDER_PORT || 11434);
const EXPECTED_KEY = process.env.FAKE_PROVIDER_KEY || 'fake-ollama-key';

const server = http.createServer((req, res) => {
  let raw = '';
  req.on('data', (c) => (raw += c));
  req.on('end', () => {
    const auth = req.headers.authorization || '';
    const okKey = auth === `Bearer ${EXPECTED_KEY}`;
    if (req.method === 'POST' && req.url === '/v1/chat/completions') {
      if (!okKey) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ error: { message: 'Invalid API key', type: 'auth' } }));
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(
        JSON.stringify({
          id: 'fake-1',
          object: 'chat.completion',
          model: 'fake-ollama-model',
          choices: [
            {
              index: 0,
              message: { role: 'assistant', content: 'pong' },
              finish_reason: 'stop',
            },
          ],
          usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
        }),
      );
    }
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'not found' } }));
  });
});

server.listen(PORT, () => console.log(`[fake-provider] listening on :${PORT}`));
