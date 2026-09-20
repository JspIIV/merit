// Prove Merit end to end on GenLayer Asimov.
//
//   AT=0x... PADV=<padv pw> PPUB=<ppub pw> node scripts/prove.mjs
//
// One program whose source page lists accepted contributors. Two addresses claim
// their own pass:
//   - padv, which IS on the list  -> QUALIFIED -> pass ISSUED
//   - ppub, which is NOT on the list -> NOT_QUALIFIED -> DENIED
// The address checked is always the caller, so nobody claims for anyone else.
import { Wallet } from 'ethers';
import { createClient, createAccount } from 'genlayer-js';
import { testnetAsimov } from 'genlayer-js/chains';
import fs from 'fs';
import os from 'os';
import path from 'path';
import url from 'url';

const AT = process.env.AT;
const PADV = process.env.PADV || '';
const PPUB = process.env.PPUB || '';
if (!AT || !PADV || !PPUB) { console.error('set AT, PADV and PPUB'); process.exit(1); }

const ROOT = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const KS = path.join(os.homedir(), '.genlayer', 'keystores');
async function acct(file, pw) {
  const w = await Wallet.fromEncryptedJson(fs.readFileSync(path.join(KS, file), 'utf8'), pw);
  return { addr: w.address.toLowerCase(), client: createClient({ chain: testnetAsimov, account: createAccount(w.privateKey) }) };
}
const padv = await acct('padv.json', PADV);   // listed contributor
const ppub = await acct('ppub.json', PPUB);   // not listed
const anybody = createClient({ chain: testnetAsimov });

const SOURCE = 'https://raw.githubusercontent.com/JspIIV/merit/master/docs/members/contributors.txt';
const NAME = 'Project Orbit contributor pass';
const REQUIREMENT = 'The claiming address is listed as an accepted contributor on the page.';

const out = [];
const say = l => { console.log(l); out.push(l); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const transient = e => /-32005|-32006|-32029|-32603|at capacity|rate limit|gas rate|reverted.*consensus|consensus.*reverted|backpressure|fetch failed|timeout|502|503|429|ECONNRESET/i
  .test(String(e?.details || e?.shortMessage || e?.message || e));

const read = async (fn, args = []) => JSON.parse(await anybody.readContract({ address: AT, functionName: fn, args }));
async function write(who, fn, args) {
  for (let a = 1; ; a++) {
    try { return await who.client.writeContract({ address: AT, functionName: fn, args, value: 0n }); }
    catch (e) { if (!transient(e) || a >= 8) throw e; say(`  (${fn} transient, wait ${8 * a}s)`); await sleep(8000 * a); }
  }
}
async function pollClaim(pid, addr, label) {
  for (let i = 0; i < 40; i++) {
    await sleep(12000);
    let r; try { r = await read('get_claim', [pid, addr]); } catch { continue; }
    if (r.exists !== false && r.status) { say(`  ${label}: ${r.status} (${(i + 1) * 12}s)`); return r; }
  }
  throw new Error('timed out polling ' + label);
}

say('Merit, proven on GenLayer Asimov');
say('  contract ' + AT);
say('  listed contributor (padv) ' + padv.addr);
say('  not listed (ppub)         ' + ppub.addr);
say('');

const before = (await read('size')).programs;
await write(padv, 'open_program', [NAME, REQUIREMENT, SOURCE]);
await sleep(8000);
let pid = null;
for (let i = 0; i < 20; i++) { const s = await read('size'); if (s.programs > before) { pid = String(s.programs - 1); break; } await sleep(4000); }
if (pid === null) throw new Error('program was not opened');
say('opened program #' + pid);
say('');

say('padv (on the list) claims its pass...');
await write(padv, 'claim', [pid]);
const c0 = await pollClaim(pid, padv.addr, 'padv claim');
say('  decision ' + c0.decision + ' -> ' + c0.status);
say('  reason: ' + (c0.reason || '(none)'));
say('');

say('ppub (not on the list) claims a pass...');
await write(ppub, 'claim', [pid]);
const c1 = await pollClaim(pid, ppub.addr, 'ppub claim');
say('  decision ' + c1.decision + ' -> ' + c1.status);
say('  reason: ' + (c1.reason || '(none)'));
say('');

const hpPadv = await read('has_pass', [pid, padv.addr]);
const hpPpub = await read('has_pass', [pid, ppub.addr]);
const size = await read('size');
say('has_pass(padv) = ' + hpPadv.has_pass + ' ; has_pass(ppub) = ' + hpPpub.has_pass);
say('register: ' + JSON.stringify(size));

const checks = [
  ['a program was opened', before === 0 && size.programs === 1],
  ['the listed address is QUALIFIED', c0.decision === 'QUALIFIED'],
  ['and its pass is ISSUED', c0.status === 'ISSUED'],
  ['the unlisted address is NOT_QUALIFIED', c1.decision === 'NOT_QUALIFIED'],
  ['and it is DENIED, no pass', c1.status === 'DENIED'],
  ['has_pass gates true only for the listed address', hpPadv.has_pass === true && hpPpub.has_pass === false],
  ['the program counts one issued and one denied', size.issued === 1 && size.denied === 1],
];
say('');
for (const [label, ok] of checks) say((ok ? '  ok   ' : ' FAIL  ') + label);
const failed = checks.filter(([, ok]) => !ok);
say('');
say(failed.length ? `${failed.length} of ${checks.length} checks failed` : `${checks.length} checks. It issued a pass only to the address the page actually showed qualifying.`);

fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'results', 'proved.json'), JSON.stringify({
  proved_at: new Date().toISOString(), network: 'genlayer testnet asimov', contract: AT,
  program: pid, source: SOURCE, requirement: REQUIREMENT,
  listed: c0, not_listed: c1, has_pass: { listed: hpPadv, not_listed: hpPpub }, size,
  checks: checks.map(([label, ok]) => ({ label, ok })), transcript: out,
}, null, 2));
say('Written to results/proved.json');
process.exit(failed.length ? 1 : 0);
