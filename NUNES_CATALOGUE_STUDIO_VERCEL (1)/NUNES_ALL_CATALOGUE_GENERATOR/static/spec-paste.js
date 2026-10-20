/* NUNES Full Catalogue: text-only, offline technical specification table parser.
   Data is imported into editable inputs for human review; not auto-verified.
   Supports Excel/TSV, Markdown pipe tables, colon rows and flattened copy.
*/
(() => {
  'use strict';
  const MAX_ROWS=100;
  const LABELS=new Set([
    'brand','manufacturer','make','model','model number','product type','instrument type',
    'machine type','type','category','product category','detection principle',
    'detection method','detection technology','measurement','measurement type',
    'measuring principle','measurement principle','measuring range','measurement range',
    'range','accuracy','resolution','sensitivity','repeatability','reproducibility',
    'maximum temperature','minimum temperature','operating temperature','temperature range',
    'analysis time','analysis speed','drift correction','test methods mentioned in source',
    'test methods','test method','standards','standard','sample materials','sample type',
    'sample size','sample weight','sample volume','applications','usage/application',
    'power supply','voltage','frequency','weight','dimensions','capacity',
    'operating method','calibration','interface','display','display type',
    'sensor type','automation grade','number of channels','channel','channels',
    'operating pressure','working temperature','model no','range of measurement',
    'measurement parameters','measurement function','testing principle'
  ]);
  const HEADERS=new Set([
    'specification','specifications','technical specification',
    'technical specifications','parameter','parameters','field','fields',
    'details','detail','value','values','description','technical details'
  ]);
  const stripStyle=s=>String(s||'').replace(/\r/g,'')
    .replace(/^\s*#{1,6}\s*/,'')
    .replace(/\*\*/g,'')
    .replace(/^\s*[-•]\s+/,'')
    .replace(/\s+/g,' ').trim();
  const keyNorm=s=>stripStyle(s).replace(/:\s*$/,'').toLowerCase();
  const separator=s=>/^\s*\|?\s*[:\-–— ]{1,}\s*\|?\s*$/.test(s)
    ||/^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$/.test(s);
  const safeKey=key=>{
    const k=stripStyle(key).replace(/:\s*$/,'');
    if(!k||k.length>85||k.split(/\s+/).length>11
      ||/https?:\/\/|www\./i.test(k)
      ||/[!?;]/.test(k))return false;
    return /^[\p{L}\p{N}][\p{L}\p{N}\s/()&.,+%°\-–—]*$/u.test(k);
  };
  const safeValue=value=>{
    const v=stripStyle(value);
    return v.length>0 && v.length<=650 && !/^[-–—|:\s]+$/.test(v);
  };
  const check=(key,value)=>{
    const k=stripStyle(key).replace(/:\s*$/,'');
    const v=stripStyle(value);
    if(!safeKey(k)||!safeValue(v)||HEADERS.has(keyNorm(k)))return null;
    return [k,v];
  };
  function parse(text){
    text=String(text||'').slice(0,35000);
    const out=[];
    const seen=new Set();
    const put=(key,value)=>{
      const pair=check(key,value);
      if(!pair)return;
      const norm=keyNorm(pair[0]);
      if(seen.has(norm)||out.length>=MAX_ROWS)return;
      seen.add(norm);out.push(pair);
    };
    const raw=text.split(/\n/).map(s=>s.trim()).filter(Boolean);
    let recognizedLayout=false;
    const unparsed=[];
    for(const line of raw){
      if(separator(line))continue;
      // Common two-column pipe table with header and Markdown separator.
      if(line.startsWith('|') && line.endsWith('|')){
        const columns=line.slice(1,-1).split('|').map(stripStyle);
        if(columns.length===2 && columns.every(Boolean)
           && !columns.every(x=>separator(x))){
          if(HEADERS.has(keyNorm(columns[0]))&&HEADERS.has(keyNorm(columns[1]))){
            recognizedLayout=true;continue;
          }
          put(columns[0],columns[1]);recognizedLayout=true;continue;
        }
        if(columns.length<=1&&(!columns[0]||separator(columns[0])))continue;
      }
      // Native spreadsheet clipboard text (Excel/Sheets) with tabs.
      if(line.includes('\t')){
        const cells=line.split('\t').map(stripStyle);
        if(cells.length>=2){
          const first=cells[0],second=cells[1];
          if(HEADERS.has(keyNorm(first))&&HEADERS.has(keyNorm(second))){
            recognizedLayout=true;continue;
          }
          put(first,second);recognizedLayout=true;continue;
        }
      }
      // Ordinary "Brand: MOL" source notes and similar labelled rows.
      const labeled=line.match(/^([\p{L}][\p{L}\p{N}\s/()&.,+%°\-–—]{1,82})\s*:\s*(.{1,650})$/u);
      if(labeled){
        const first=labeled[1].trim();
        if(!HEADERS.has(keyNorm(first))){
          put(first,labeled[2]);recognizedLayout=true;continue;
        }
      }
      unparsed.push(line.replace(/^\|\s*/,'').replace(/\s*\|$/,'').trim());
    }
    const cells=unparsed.map(stripStyle)
      .filter(s=>s&&!separator(s)&&!/^\|+$/.test(s));
    // Markdown copied from ChatGPT sometimes flattens a 2-column table into:
    // Specification, Details, Brand, MOL, Model, CS1000 / CS1500, ...
    // Each pair was separated by a blank, one-cell "| |" table.
    const header=(
      cells.length>=2
      && HEADERS.has(keyNorm(cells[0]))
      && HEADERS.has(keyNorm(cells[1]))
    );
    const start=header?2:0;
    const plausibleUnheaded=cells.length>=4&&LABELS.has(keyNorm(cells[0]));
    if(header||plausibleUnheaded){
      for(let i=start;i+1<cells.length&&out.length<MAX_ROWS;i+=2){
        put(cells[i],cells[i+1]);
      }
      recognizedLayout=true;
    }else if(cells.length===2&&HEADERS.has(keyNorm(cells[0]))){
      // A pasted column label and one cell is not enough to guess its pairing.
      recognizedLayout=false;
    }
    return {rows:out,recognized:recognizedLayout&&out.length>0,
      imported:out.length};
  }
  if(typeof window!=='undefined'){
    Object.defineProperty(window,'NUNESSpecPaste',{
      value:Object.freeze({parse,MAX_ROWS}),
      configurable:false,writable:false
    });
  }
})();
