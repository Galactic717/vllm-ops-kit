import http from 'k6/http';
import { check } from 'k6';

const profile = __ENV.PROFILE || 'smoke';
const base = __ENV.BASE_URL || 'http://127.0.0.1:18080';
const rate = Number(__ENV.BASE_RATE || '5');
const duration = { smoke: '12s', spike: '35s', soak: '10m' }[profile];
if (!duration) throw new Error('PROFILE must be smoke, spike or soak');

export const options = {
  scenarios: {
    requests: {
      executor: 'constant-arrival-rate',
      rate: profile === 'spike' ? rate * 3 : rate,
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 6,
      maxVUs: 30,
    },
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max', 'count'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{operation:chat}': ['p(95)<1500'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count==0'],
  },
};

export default function () {
  const reply = http.post(base + '/v1/chat/completions', JSON.stringify({
    model: __ENV.MODEL || 'ops-fixture',
    messages: [{ role: 'user', content: 'Say hello' }],
    max_tokens: 8,
  }), {
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + __ENV.GATEWAY_KEY },
    tags: { operation: 'chat' },
    timeout: '5s',
  });
  check(reply, {
    'chat returned generated text': (res) => res.status === 200 && !!res.json('choices.0.message.content'),
  });
  const workflows = http.get(base + '/workflows', {
    headers: { Authorization: 'Bearer ' + __ENV.VERSTAK_TOKEN },
    tags: { operation: 'workflows' },
    timeout: '5s',
  });
  check(workflows, { 'workflows API is authenticated': (res) => res.status === 200 });
}
