// Captura "antes" e "depois" (desktop e mobile) e junta numa imagem só, lado a lado.
// Uso: node comparar-visual.mjs --antes URL --depois URL --saida caminho.png
// Requer: npm i -D playwright && npx playwright install chromium (pedir permissão ao usuário antes).
import { chromium } from 'playwright';

const arg = (k) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : undefined; };
const antes = arg('antes'), depois = arg('depois'), saida = arg('saida') || 'comparacao.png';
if (!antes || !depois) { console.error('Uso: --antes URL --depois URL [--saida arquivo.png]'); process.exit(1); }

const telas = [{ nome: 'desktop', width: 1440, height: 900 }, { nome: 'mobile', width: 390, height: 844 }];
const browser = await chromium.launch();
const shots = {};
for (const t of telas) for (const [rotulo, url] of [['antes', antes], ['depois', depois]]) {
  const page = await browser.newPage({ viewport: { width: t.width, height: t.height } });
  await page.goto(url, { waitUntil: 'networkidle' });
  shots[`${t.nome}-${rotulo}`] = (await page.screenshot()).toString('base64');
  await page.close();
}
const img = (k) => `<figure><figcaption>${k}</figcaption><img src="data:image/png;base64,${shots[k]}"></figure>`;
const html = `<style>body{margin:0;font:14px sans-serif;background:#fff}.l{display:flex;gap:16px;padding:8px;align-items:flex-start}
figure{margin:0}img{display:block;border:1px solid #ccc;max-width:720px}figcaption{padding:4px 0;font-weight:600}</style>
<div class="l">${img('desktop-antes')}${img('desktop-depois')}</div><div class="l">${img('mobile-antes')}${img('mobile-depois')}</div>`;
const page = await browser.newPage({ viewport: { width: 1500, height: 800 } });
await page.setContent(html);
await page.screenshot({ path: saida, fullPage: true });
await browser.close();
console.log(`comparação salva em ${saida}`);
