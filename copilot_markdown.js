// Convert only the response subtree to portable Markdown; never copy executable HTML.
((root) => {
  const escape = text => text.replace(/\\/g, '\\\\').replace(/([`*_[\]<>])/g, '\\$1');
  const children = node => Array.from(node.childNodes).map(walk).join('');
  function fence(text, language = '') {
    const lengths = Array.from(text.matchAll(/`+/g), m => m[0].length);
    const ticks = '`'.repeat(Math.max(3, ...lengths.map(n => n + 1)));
    return '\n\n' + ticks + language + '\n' + text.replace(/\n$/, '') + '\n' + ticks + '\n\n';
  }
  function language(node) {
    const identity=node.closest('.scriptor-component-code-block')?.querySelector('[data-testid="one-copilot-code-identity"]');
    const label=identity?.textContent.trim().toLowerCase();
    if (label && /^[\w+#.-]{1,30}$/.test(label)) return label;
    const code = node.matches('code') ? node : node.querySelector('code');
    const match = (code?.className || node.className || '').toString().match(/(?:language|lang)-([\w+-]+)/);
    if (match) return match[1];
    for (let p = node.parentElement, i = 0; p && i < 3 && p !== root; p = p.parentElement, i++) {
      const label = (p.innerText || '').split('\n').find(s => /^(python|javascript|typescript|json|html|css|bash|cmd|sql|text|xml|yaml|powershell|csharp|java)$/i.test(s.trim()));
      if (label) return label.trim().toLowerCase();
    }
    return '';
  }
  function walk(node) {
    if (node.nodeType === 3) return escape(node.textContent.replace(/\s+/g, ' '));
    if (node.nodeType !== 1) return '';
    const tag = node.tagName.toLowerCase();
    if (['script','style','button','svg','noscript','input','textarea'].includes(tag) || node.hidden || node.getAttribute('aria-hidden') === 'true') return '';
    if (node.classList.contains('scriptor-component-code-block')) {
      const editor=node.querySelector('[aria-label="Code editor"]');
      if (editor) return walk(editor);
    }
    if (tag === 'pre') return fence(node.querySelector('code')?.textContent || node.textContent || '', language(node));
    if (node.getAttribute('aria-label') === 'Code editor') {
      const lines = Array.from(node.querySelectorAll('[data-line-index]')).sort((a,b) => Number(a.dataset.lineIndex)-Number(b.dataset.lineIndex));
      return fence(lines.length ? lines.map(e => e.getAttribute('data-line-empty') === 'true' ? '' : e.textContent.replace(/\u00a0/g, ' ')).join('\n') : node.textContent || '', language(node));
    }
    if (tag === 'code') {
      const text = node.textContent || '';
      const delimiter = '`'.repeat(Math.max(1, ...Array.from(text.matchAll(/`+/g), m => m[0].length + 1)));
      const pad = text.startsWith('`') || text.endsWith('`') || /^ .* $/.test(text) ? ' ' : '';
      return delimiter + pad + text + pad + delimiter;
    }
    if (tag === 'table') {
      const rows = Array.from(node.querySelectorAll('tr')).filter(tr => tr.closest('table') === node).map(tr => Array.from(tr.children).filter(e => /^(TH|TD)$/.test(e.tagName)).map(e => children(e).trim().replace(/\|/g, '\\|').replace(/\n+/g, ' · ')));
      if (!rows.length) return '';
      const width = Math.max(...rows.map(r => r.length));
      const row = values => '| ' + Array.from({length:width}, (_,i) => values[i] || '').join(' | ') + ' |';
      return '\n\n' + [row(rows[0]),row(Array(width).fill('---')),...rows.slice(1).map(row)].join('\n') + '\n\n';
    }
    if (tag === 'ul' || tag === 'ol') {
      let count = Number(node.getAttribute('start')) || 1;
      const items = Array.from(node.children).filter(e => e.tagName === 'LI').map(li => {
        const text = children(li).trim();
        const prefix = tag === 'ol' ? count++ + '. ' : '- ';
        return prefix + text.replace(/\n/g, '\n' + ' '.repeat(prefix.length));
      });
      return '\n\n' + items.join('\n') + '\n\n';
    }
    const content = children(node);
    if (/^h[1-6]$/.test(tag)) return '\n\n' + '#'.repeat(Number(tag[1])) + ' ' + content.trim() + '\n\n';
    if (tag === 'strong' || tag === 'b') return '**' + content.trim() + '**';
    if (tag === 'em' || tag === 'i') return '*' + content.trim() + '*';
    if (tag === 's' || tag === 'del') return '~~' + content.trim() + '~~';
    if (tag === 'blockquote') return '\n\n' + content.trim().split('\n').map(line => '> ' + line).join('\n') + '\n\n';
    if (tag === 'a') {
      const href = node.getAttribute('href') || '';
      if (/^https?:\/\//i.test(href)) return '[' + (content.trim() || escape(href)) + '](' + href.replace(/\(/g,'%28').replace(/\)/g,'%29').replace(/\s/g,'%20') + ')';
      return content; // blob/sandbox links are handled exclusively by real artifact downloads.
    }
    if (tag === 'img') return escape(node.getAttribute('alt') || '');
    if (tag === 'br') return '\n';
    if (tag === 'hr') return '\n\n---\n\n';
    if (['p','div','section','article'].includes(tag)) return '\n\n' + content.trim() + '\n\n';
    return content;
  }
  // Do not normalize blank lines globally: code whitespace must survive intact.
  return children(root).trim();
})
