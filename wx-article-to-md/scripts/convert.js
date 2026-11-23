(() => {
  const c = document.getElementById('js_content');
  if (!c) return { err: 'no js_content' };
  const TAG = { math:'math', mrow:'mrow', mi:'mi', mo:'mo', mn:'mn', mtext:'mtext', text:'mtext', mspace:'mspace', msub:'msub', msup:'msup', msubsup:'msubsup', mfrac:'mfrac', msqrt:'msqrt', mroot:'mroot', mover:'mover', munder:'munder', munderover:'munderover', mtable:'mtable', mtr:'mtr', mlabeledtr:'mtr', mtd:'mtd', mstyle:'mrow', mpadded:'mrow', menclose:'mrow', TeXAtom:'mrow', mphantom:'mphantom', semantics:'mrow', merror:'mrow', maction:'mrow', maligngroup:'mrow', malignmark:'mrow' };
  const TOKEN = { mi:1, mo:1, mn:1, mtext:1, text:1, ms:1 };
  const PIECE = { 0x239B:'(',0x239C:'(',0x239D:'(',0x239E:')',0x239F:')',0x23A0:')',0x23A1:'[',0x23A2:'[',0x23A3:'[',0x23A4:']',0x23A5:']',0x23A6:']',0x23A7:'{',0x23A8:'{',0x23A9:'{',0x23AA:'{',0x23AB:'}',0x23AC:'}',0x23AD:'}',0x23AF:'',0x23B0:'{',0x23B1:'}' };
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  function tokenText(g, isMo){
    let out='';
    g.querySelectorAll('path[data-c], tspan').forEach(el=>{
      if(el.tagName.toLowerCase()==='path'){
        const cp=parseInt(el.getAttribute('data-c'),16);
        if(!cp) return;
        if(cp>=0xE000 && cp<=0xF8FF) return;
        if(isMo && PIECE[cp]!==undefined){
          const ch=PIECE[cp];
          if(ch){
            if(out.endsWith(ch)) return;
            out+=ch;
          }
          return;
        }
        out+=String.fromCodePoint(cp);
      } else out+=el.textContent;
    });
    return out;
  }
  function topChildren(g){
    const res=[];
    (function walk(node){
      for(const ch of node.children){
        const tg=ch.tagName.toLowerCase();
        if(tg==='g' && ch.hasAttribute('data-mml-node')) res.push(ch);
        else if(tg==='g' || tg==='svg') walk(ch);
      }
    })(g);
    return res;
  }
  function xOf(g){
    const m=(g.getAttribute('transform')||'').match(/translate\(\s*([-\d.]+)/);
    return m?parseFloat(m[1]):null;
  }
  function mml(g){
    const t=g.getAttribute('data-mml-node')||'mrow';
    const kind=TAG[t]||'mrow';
    if(TOKEN[t]) return '<'+kind+'>'+esc(tokenText(g, t==='mo'))+'</'+kind+'>';
    if(t==='mspace'){
      let w=0.167;
      const x=xOf(g), s=g.nextElementSibling;
      const x2=s?(xOf(s)===null?0:xOf(s)):null;
      if(x!==null && x2!==null && x2>x) w=Math.min((x2-x)/1000, 3);
      return '<mspace width="'+w.toFixed(3)+'em"></mspace>';
    }
    if(t==='mtable'){
      const kids0=topChildren(g);
      const rows=[], strays=[];
      for(const ch of kids0){
        const k=ch.getAttribute('data-mml-node');
        if(k==='mtr'||k==='mlabeledtr') rows.push(mml(ch));
        else if(k==='mtd') strays.push(mml(ch));
      }
      if(strays.length){
        if(rows.length){
          const last=rows.length-1;
          rows[last]=rows[last].replace(/<\/mtr>$/,'')+strays.join('')+'</mtr>';
        } else rows.push('<mtr>'+strays.join('')+'</mtr>');
      }
      return '<mtable>'+rows.join('')+'</mtable>';
    }
    const kids=topChildren(g);
    const parts=kids.map(mml);
    if(t==='munder' && parts[1]==='<mo></mo>') parts[1]='<mo>\u23DF</mo>';
    if(t==='mover' && parts[1]==='<mo></mo>') parts[1]='<mo>\u23DE</mo>';
    if(t==='munderover'){
      if(parts[1]==='<mo></mo>') parts[1]='<mo>\u23DF</mo>';
      if(parts[2]==='<mo></mo>') parts[2]='<mo>\u23DE</mo>';
    }
    if(t==='msqrt'||t==='mroot'){
      const keep=parts.filter(p=>p!=='<mo>\u221A</mo>'&&p!=='<mo>\u221B</mo>');
      if(keep.length===1 && keep[0].indexOf('<mrow>')===0){
        return '<'+kind+'>'+keep[0]+'</'+kind+'>';
      }
      return '<'+kind+'>'+keep.join('')+'</'+kind+'>';
    }
    const inner=parts.join('');
    if(!kids.length){
      const txt=tokenText(g, t==='mo');
      if(txt) return '<mtext>'+esc(txt)+'</mtext>';
    }
    return '<'+kind+'>'+inner+'</'+kind+'>';
  }
  const meta={
    title:(document.getElementById('activity-name')?.textContent||document.title||'').trim(),
    account:(document.getElementById('js_name')?.textContent||'').trim(),
    date:(document.getElementById('publish_time')?.textContent||'').trim(),
    url:location.href
  };
  let n=0;
  c.querySelectorAll('[data-owc-math]').forEach(el=>{
    const root=el.querySelector('g[data-mml-node="math"]');
    if(!root) return;
    const disp=(el.getAttribute('data-owc-math')==='block')||el.tagName.toLowerCase()==='section';
    let m=mml(root);
    m=m.replace('<math>','<math xmlns="http://www.w3.org/1998/Math/MathML" display="'+(disp?'block':'inline')+'">');
    el.innerHTML=m;
    n++;
  });
  c.querySelectorAll('img').forEach(im=>{
    const ds=im.getAttribute('data-src');
    if(ds) im.setAttribute('src', ds);
  });
  c.querySelectorAll('script,style,iframe,mpvoice,mp-common-profile,mp-common-music,svg').forEach(e=>e.remove());
  c.querySelectorAll('*').forEach(el=>{
    if(el.closest('math')) return;
    const tag=el.tagName;
    if(tag==='IMG'||tag==='A'||tag==='PRE'||tag==='CODE') return;
    for(const a of [...el.attributes]) el.removeAttribute(a.name);
  });
  c.querySelectorAll('span').forEach(s=>{ while(s.firstChild) s.parentNode.insertBefore(s.firstChild,s); s.remove(); });
  function b64(s){
    const bytes=new TextEncoder().encode(s);
    let bin=''; const CH=0x8000;
    for(let i=0;i<bytes.length;i+=CH) bin+=String.fromCharCode.apply(null,bytes.subarray(i,i+CH));
    return btoa(bin);
  }
  const html=c.innerHTML;
  window.__wx={b64:b64(html), meta:meta, len:html.length, converted:n};
  return {ok:true,converted:n,len:html.length,b64len:window.__wx.b64.length,meta:meta};
})()
