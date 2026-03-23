const PROXY = '/v1';
const API = '/api';

export async function fetchJSON(url: string) {
	const r = await fetch(url + '?' + Date.now());
	return r.ok ? r.json() : null;
}

export async function postJSON(url: string, body?: unknown) {
	const r = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: body ? JSON.stringify(body) : undefined
	});
	return r.json();
}

// Proxy APIs
export const getProxyInfo = () => fetchJSON(`${PROXY}/`);
export const getModels = () => fetchJSON(`${PROXY}/models`);
export const getProviders = () => fetchJSON(`${PROXY}/providers`);
export const getProxyLogs = () => fetchJSON(`${PROXY}/logs`);
export const getSkills = () => fetchJSON(`${PROXY}/rag/skills`);
export const getSessions = () => fetchJSON(`${PROXY}/rag/sessions`);
export const reloadProviders = () => fetchJSON(`${PROXY}/reload`);

// Dashboard APIs
export const getKeys = () => fetchJSON(`${API}/keys`);
export const saveKeys = (keys: Record<string, string>) => postJSON(`${API}/keys`, keys);
export const testOneKey = (env_name: string) => postJSON(`${API}/test-one-key`, { env_name });
export const startScan = () => postJSON(`${API}/scan`);
export const startTestKeys = () => postJSON(`${API}/test-keys`);
export const startBrain = () => postJSON(`${API}/brain`);
export const getDashLogs = () => fetchJSON(`${API}/logs`);
export const getBrainLogs = () => fetchJSON(`${API}/brain/logs`);
export const getBrainRecs = () => fetchJSON(`${API}/brain/recommendations`);
export const getData = () => fetchJSON(`${API}/data`);
export const getStatus = () => fetchJSON(`${API}/status`);

// Chat test
export async function testChat(model = 'auto', message = 'Hi') {
	return postJSON(`${PROXY}/chat/completions`, {
		model,
		messages: [{ role: 'user', content: message }],
		max_tokens: 20
	});
}
