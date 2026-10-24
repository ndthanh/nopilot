'use strict';
(() => {
  const md = window.markdownit({html:false, linkify:true, breaks:true, maxNesting:30,
    highlight(text, language) {
      if (text.length <= 100000 && language && window.hljs?.getLanguage(language)) {
        try { return hljs.highlight(text,{language,ignoreIllegals:true}).value; } catch (_) {}
      }
      return ''; // markdown-it escapes the original code.
    }
  });
  md.validateLink = url => /^https?:\/\//i.test(url);
  md.linkify.set({fuzzyEmail:false});
  md.renderer.rules.image = (tokens,index) => md.utils.escapeHtml(tokens[index].content || 'Ảnh');
  const linkOpen = md.renderer.rules.link_open || ((tokens,index,options,env,self) => self.renderToken(tokens,index,options));
  md.renderer.rules.link_open = (tokens,index,options,env,self) => {
    tokens[index].attrSet('target','_blank');tokens[index].attrSet('rel','noopener noreferrer');
    return linkOpen(tokens,index,options,env,self);
  };
  window.nopilotMarkdown = (node, text) => {
    node.classList.add('markdown-body');
    node.innerHTML = md.render(String(text || ''));
    for (const table of node.querySelectorAll('table')) {
      const wrap = document.createElement('div');wrap.className='markdown-table';wrap.tabIndex=0;
      wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Bảng trong câu trả lời');
      table.replaceWith(wrap);wrap.append(table);
    }
    for (const pre of node.querySelectorAll('pre')) {
      const code=pre.querySelector('code');if(!code)continue;
      const wrap=document.createElement('div');wrap.className='code-block';
      const bar=document.createElement('div');bar.className='code-toolbar';
      const label=document.createElement('span');label.textContent=code.className.match(/language-([^\s]+)/)?.[1] || 'code';
      const copy=document.createElement('button');copy.type='button';copy.textContent='Copy';copy.setAttribute('aria-label','Sao chép mã '+label.textContent);
      copy.onclick=async()=>{
        try {await navigator.clipboard.writeText(code.textContent);copy.textContent='Đã sao chép';}
        catch (_) {copy.textContent='Không sao chép được';}
        setTimeout(()=>{copy.textContent='Copy';},1800);
      };
      pre.replaceWith(wrap);bar.append(label,copy);wrap.append(bar,pre);
    }
  };
})();
