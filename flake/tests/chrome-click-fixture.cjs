// Execute the real geometry expression with a small, deterministic DOM.
const fs = require('node:fs');
const request = JSON.parse(process.argv[2]);
const state = process.argv[3];
const mode = process.env.FAKE_CLICK_CASE;
const rect = {x: 10, y: mode === 'offscreen' ? 2200 : 20, width: mode === 'hidden' ? 0 : 20, height: 10};
const element = {
  getBoundingClientRect: () => rect,
  matches: () => mode === 'disabled',
  getAttribute: () => null,
  contains: other => other === element,
  scrollIntoView: () => { rect.y = 20; fs.writeFileSync(state + '/scrolled', 'yes'); },
};
global.window = {scrollX: mode === 'scrolled' ? 100 : 0, scrollY: mode === 'scrolled' ? 2000 : 0};
global.document = {
  querySelector: () => mode === 'missing' ? null : element,
  elementFromPoint: () => mode === 'covered' ? {} : element,
};
const value = eval(request.params.expression);
process.stdout.write(JSON.stringify({id: request.id, result: {result: {type: typeof value, value}}}) + '\n');
