// Cloudflare Worker: fires the "Collect Ottawa Data" GitHub workflow on a cron.
// GitHub's own schedule: trigger is throttled on this account; workflow_dispatch isn't.
// Secrets (wrangler secret put): GITHUB_TOKEN  (fine-grained PAT, this repo only,
// "Actions: Read and write" permission, nothing else).

const REPO = "OttawaVisuals/Ottawa-Visuals";
const WORKFLOW = "collect.yml";

async function dispatch(env) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ottawa-visuals-cron",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  // 204 = accepted. Throwing makes the failure show in the Worker's logs.
  if (res.status !== 204) {
    throw new Error(`dispatch failed: ${res.status} ${await res.text()}`);
  }
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(dispatch(env));
  },
  // Visiting the Worker URL does nothing (no way to trigger runs by hand/by others).
  async fetch() {
    return new Response("ok", { status: 200 });
  },
};
