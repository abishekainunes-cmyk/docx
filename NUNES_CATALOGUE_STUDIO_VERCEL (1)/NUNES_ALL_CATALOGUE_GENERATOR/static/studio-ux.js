/* NUNES Catalogue Studio 2026 — accessible, progressive enhancements.
   Preserve original Flask endpoints and do not invent product facts. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  function node(tag, className, textValue) {
    const n=document.createElement(tag);
    if (className) n.className=className;
    if (textValue !== undefined) n.textContent=textValue;
    return n;
  }
  const mini=location.pathname==='/mini-catalogue';
  const examples=[
    'RMS Digital Multimeter','Leak Detector Kit','Abbott Blood Analyzer',
    'Digital Automatic Pyrogen Telethermometer','Digital Potentiometric Titration Apparatus',
    'Multi-Position Magnetic Stirrer'
  ];
  document.documentElement.classList.add('studio-upgraded');
  // Header reflects the working catalogue page; no unverified badges.
  const brand=document.querySelector('.brand');
  if(brand){
    const strong=brand.querySelector('strong'), subtitle=brand.querySelector('span');
    if(strong) strong.textContent='NUNES  /  Catalogue Studio';
    if(subtitle)subtitle.textContent='Automated Catalogue Generator • Nunes Instrumentation';
  }
  const page=document.querySelector('.pagehead');
  if(page){
    const title=$('page-title');
    if(title) title.textContent=mini?'Mini Catalogue (Grid & List)':'Full Catalogue (2 Pages)';
    const eyebrow=page.querySelector('.eyebrow');
    if(eyebrow)eyebrow.textContent='NUNES CATALOGUE STUDIO';
    const intro=page.querySelector('p');
    if(intro)intro.textContent='Research genuine product records, review details and create a branded PDF.';
    const download=node('button','btn nav-download','↓ Download PDF');
    download.id='quick-download';
    download.type='button';
    download.disabled=true;
    download.addEventListener('click',()=>{if(!$('download').disabled)$('download').click();});
    page.append(download);
    const origin=$('download');
    const watch=new MutationObserver(()=>{download.disabled=origin.disabled});
    watch.observe(origin,{attributes:true,attributeFilter:['disabled']});
  }
  // Display labels, not fabricated specs or images. Chips populate real inputs.
  const quick=node('section','quick-tests');
  quick.append(node('span','quick-heading','Quick Test Instruments'));
  const chips=node('div','quick-chips');
  for(const name of examples){
    const b=node('button','sample-chip',name);
    b.type='button';
    b.addEventListener('click',()=>{
      $('q').value=name;
      $('product').value=name;
      $('model').value='';
      $('specs').value='';
      $('description').value='';
      $('features').value='';
      $('image').value='';
      if($('indiamart-url'))$('indiamart-url').value='';
      if($('editbadge'))$('editbadge').textContent='Sample name — research required';
      $('specs').dispatchEvent(new Event('input',{bubbles:true}));
      $('q').focus();
      const note=$('searchmsg');
      if(note){note.hidden=false;note.textContent='Product selected. Upload its actual photo, then prepare the draft. Sample specifications are not supplied.';}
    });
    chips.append(b);
  }
  quick.append(chips);
  const grid=document.querySelector('#workarea > .grid');
  if(grid)grid.before(quick);
  const sourceTitle=node('div','source-heading','Source Evidence');
  $('source-links')?.before(sourceTitle);
  const researchStatus=$('source-research');
  if(researchStatus)researchStatus.setAttribute('aria-live','polite');
  // Clearly distinguish a sourced listing from product verification.
  const search=$('products');
  if(search){
    const h=search.querySelector('.card-h h2');
    if(h)h.textContent='1-Click Product Research & AI Draft';
    const form=search.querySelector('.body');
    if(form){
      const label=node('label','search-label','Product Name or Model *');
      label.htmlFor='q';
      form.querySelector('.searchbar')?.before(label);
      const image=$('search-image-file');
      if(image){
        const uploadLabel=node('label','upload-label','Upload Photo  ·  Studio Cutout');
        uploadLabel.htmlFor='search-image-file';
        image.before(uploadLabel);
        const explainer=node('p','small muted upload-note','Use a real product photo. Background removal applies when the image is supported.');
        image.after(explainer);
      }
      if(!mini){
        const btn=$('generate-ai');
        if(btn){
          const holder=node('div','research-action');
          form.insertBefore(holder,$('source-research'));
          holder.append(btn);
          btn.classList.add('full');
          const original=document.querySelector('#editor .section-action:empty');
          if(original)original.hidden=true;
        }
      }
    }
  }

  // Paste -> deterministic autofill -> review. Gemini remains available separately
  // for improvement, but no network call is required for supplied structured facts.
  if (!mini && $('products') && $('editor')) {
    const parent=$('products').querySelector('.body');
    const panel=node('section','paste-autofill');
    panel.style.cssText='margin-top:14px;padding:12px;border:1px solid #dbeafe;border-radius:10px;background:#f8fbff';
    const heading=node('label','','Paste Product Details (any format)');
    heading.htmlFor='pasted-details';
    const area=node('textarea','');
    area.id='pasted-details';
    area.rows=8;
    area.placeholder='Paste product name, description, key features and specifications here. No manual copying into separate fields.';
    const controls=node('div','row');
    controls.style.cssText='display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:9px';
    const fill=node('button','btn','Auto-Fill All Details with AI');
    fill.type='button';
    const replaceLabel=node('label','');
    replaceLabel.style.cssText='display:flex;gap:6px;align-items:center;margin:0;font-size:12px';
    const replace=node('input',''); replace.type='checkbox';replace.style.width='auto';
    replaceLabel.append(replace,document.createTextNode('Replace existing details'));
    controls.append(fill,replaceLabel);
    const report=node('div','notice');
    report.id='autofill-report';
    report.setAttribute('role','status');
    panel.append(heading,area,controls,report);
    parent.append(panel);
    const previousAutofill=new Map();
    const setField=(id,value)=>{
      const input=$(id);if(!input||!value)return false;
      // Refresh previously imported data but preserve manual operator edits.
      const existing=input.value.trim();
      if(existing&&!replace.checked&&previousAutofill.get(id)!==existing)return false;
      input.value=value; input.dispatchEvent(new Event('input',{bubbles:true}));
      previousAutofill.set(id,String(value).trim());
      return true;
    };
    const headings={
      description:/^(?:product\s+)?description(?:\s*\(.*\))?$/i,
      features:/^(?:key\s+)?features?$/i,
      specs:/^(?:technical\s+)?specifications?(?:\s*(?:\/|&)\s*additional\s*details)?(?:\s*\(.*\))?$/i,
      applications:/^(?:uses?\s*\/\s*)?applications?$/i,
      source:/^(?:source\s+(?:evidence|excerpts?|links?)|references?|ai\s+draft\s+(?:description|key\s+features))\s*(?:\(.*\))?$/i
    };
    function parseDetails(text){
      // Remove Markdown emphasis before bullet prefixes. The reference
      // example uses **bold headings**, so stripping "*" first breaks them.
      const clean=s=>s.replace(/^\s*#{1,4}\s*/,'')
        .replace(/\*\*/g,'')
        .replace(/^\s*[-*•]\s*/,'')
        .replace(/\*$/,'').trim();
      const lines=text.split(/\r?\n/).map(clean).filter(s=>s.replace(/[|\-\s]/g,'').length>0);
      let section='',product='',brand='',model='',description=[],features=[],applications=[],specs=[],warnings=[];
      let pending='';
      const pair=(key,val)=>{
        key=key.replace(/[:*]/g,'').trim();val=val.trim().replace(/^\|?[-\s|]+\|?$/,'');
        if(!key||!val||/^[-|]+$/.test(key))return;
        if(/^brand$/i.test(key))brand=val;
        else if(/^(?:model(?:\s*(?:number|no\.?))?)$/i.test(key)){
          if(model&&model.toLowerCase()!==val.toLowerCase()){warnings.push(val);}
          else model=val;
        }
        else if(/^(?:product\s+)?name$/i.test(key))product=val;
        else if(!/^(?:parameter|value|technical specifications)$/i.test(key))specs.push([key,val]);
      };
      for(let i=0;i<lines.length;i++){
        let line=lines[i]; if(!line||/^\|?\s*:?-{2,}/.test(line))continue;
        let isHeading=false;
        for(const [name,re] of Object.entries(headings)){
          if(re.test(line.replace(/:$/,''))){section=name;pending='';isHeading=true;break;}
        }
        if(isHeading)continue;
        // Closing company copy is generated by the PDF template; do not
        // accidentally import it as another "Applications" bullet.
        if(/^Nunes Instrumentation supplies\b|^Final technical configuration\b/i.test(line)){
          section='source';continue;
        }
        const labeled=line.match(/^(Product Name|Brand|Model(?: Number| No\.?)?)\s*:\s*(.+)$/i);
        if(labeled){pair(labeled[1],labeled[2]);continue}
        if(/^(Product Name|Brand|Model(?: Number| No\.?)?)$/i.test(line)){
          pending=line;continue;
        }
        if(pending){if(/^extracted$/i.test(line))continue;pair(pending,line);pending='';continue}
        if(section==='source')continue;
        // Google / manufacturer snippets often contain labelled specification
        // rows before a heading, or under 'Product Details' rather than Specs.
        const knownSpec=/^(?:brand|manufacturer|model(?:\s*(?:number|no\.?))?|(?:instrument|product|stirrer|sensor|display)\s+type|type|material|top\s+plate(?:\s+material)?|body(?:\s+material)?|number\s+of\s+positions|stirring\s+positions|stirring\s+capacity|maximum\s+stirring\s+volume|speed\s+range|speed\s+control|heating(?:\s+plate)?|power\s+supply|(?:operating\s+)?voltage|capacity|(?:measurement|measuring|testing|temperature|pressure)\s+range|accuracy|resolution|repeatability|sensitivity|display|sensor|(?:number\s+of\s+)?channels?|dimensions|weight|(?:operating|working)\s+temperature|frequency|power\s+consumption|country\s+of\s+origin|throughput|sample\s+volume|automation\s+grade|interface|technology)$/i;
        const inlinePair=line.match(/^([^:|]{2,70})\s*[:|]\s*(.{1,180})$/);
        if(inlinePair&&(section==='specs'||knownSpec.test(inlinePair[1].trim()))){
          if(knownSpec.test(inlinePair[1].trim()))pair(inlinePair[1],inlinePair[2]);
          continue;
        }
        if(!product&&!section&&line.length>8&&!/^(?:source|extracted)$/i.test(line)) {
          product=line.replace(/^["“]|["”]$/g,'').replace(/\s+[–—-]\s+Model\s+.*$/i,'').trim();
          const m=line.match(/\bModel\s*(?:Number|No\.?)?\s*:?\s*([A-Za-z0-9-]{4,})/i);
          if(m&&!model)model=m[1];
          continue;
        }
        // Reference briefs commonly start with two descriptive paragraphs
        // directly under the bold product title, without a Description heading.
        if(!section && product && line.length>=38 &&
           !/^(?:model|brand|source|reference|specification)/i.test(line)){
          description.push(line);continue;
        }
        if(section==='description'){description.push(line);continue}
        if(section==='features'){features.push(line);continue}
        if(section==='applications'){applications.push(line);continue}
        if(section==='specs'){
          let m=line.match(/^([^:|]{2,90})\s*:\s*(.+)$/);
          if(m){pair(m[1],m[2]);continue}
          const parts=line.split('|').map(s=>s.trim()).filter(Boolean);
          if(parts.length===2){pair(parts[0],parts[1]);continue}
          if(i+1<lines.length && !line.includes(':') && !/^parameter|value$/i.test(line)){
            let next=lines[i+1];
            if(next&&!next.includes(':')&&!Object.values(headings).some(re=>re.test(next))){
              pair(line,next);i++;continue;
            }
          }
        }
      }
      // Prefer explicit metadata, and include it as visible specification rows.
      if(brand)specs.unshift(['Brand',brand]);
      if(model)specs.unshift(['Model',model]);
      const unique=new Map();
      for(const [k,v] of specs){if(k&&v&&!unique.has(k.toLowerCase()))unique.set(k.toLowerCase(),k+': '+v)}
      const ids=(text.match(/\b(?:[A-Z]{1,6}-?\d{2,}[A-Z0-9-]*|\d{2,}[A-Z]{1,6}\d+[A-Z0-9]*)\b/g)||[]);
      const distinct=[...new Set(ids.filter(x=>x.length>=5))];
      if(model){
        for(const other of distinct){if(other.toUpperCase()!==model.toUpperCase()&&!warnings.includes(other))warnings.push(other)}
      }
      // The example supplied in the brief contains two different models:
      // 30VT01 and 30MMS01. Flag and exclude the conflicting model sentence
      // rather than silently publishing a wrong model in the catalogue.
      const safeDescription=[];
      for(const line of description){
        for(const sentence of line.split(/(?<=[.!?])\s+/)){
          const mentions=[...sentence.matchAll(/\bModel\s*(?:Number\s*|No\.?\s*)?:?\s*([A-Za-z0-9_-]{3,35})/gi)];
          const conflicts=mentions.map(m=>m[1]).filter(value=>model&&
            value.toLowerCase()!==model.toLowerCase()&&/\d/.test(value));
          if(conflicts.length){
            for(const mismatch of conflicts)if(!warnings.includes(mismatch))warnings.push(mismatch);
            continue;
          }
          if(sentence.trim())safeDescription.push(sentence.trim());
        }
      }
      return {product,brand,model,description:safeDescription.join('\n\n').trim(),
        features:features.join('\n').trim(),applications:applications.join('\n').trim(),
        specifications:[...unique.values()].join('\n'),warnings};
    }
    // Background public research feeds the same user-visible paste parser.
    document.addEventListener('nunes:research-autofill',event=>{
      const data=event.detail||{};
      if(!data.product)return;
      const oldProduct=$('product').value.trim();
      const different=oldProduct&&oldProduct.toLowerCase()!==String(data.product).toLowerCase();
      if(different){
        for(const id of ['product','model','specs','description','features','applications']){
          const control=$(id);if(control){control.value='';control.dispatchEvent(new Event('input',{bubbles:true}));}
        }
      }
      const lines=['Product Name: '+data.product];
      if(data.model)lines.push('Model Number: '+data.model);
      if(data.description&&data.description.trim()&&!/get info of suppliers|manufacturers, exporters|find here online price|dealers, traders|latest price|at best price|also get|verified companies|id:\s*\d{7,}|price list|contact supplier/i.test(data.description))
        lines.push('Product Description',data.description.trim());
      if(data.specifications&&data.specifications.trim())
        lines.push('Technical Specifications',data.specifications.trim());
      if(Array.isArray(data.features)&&data.features.length)
        lines.push('Key Features',...data.features.map(x=>'- '+x));
      area.value=lines.join('\n');
      fill.click();
      report.textContent+=' Public research is unverified; please confirm the model before publishing.';
    });
    fill.addEventListener('click',()=>{
      const raw=area.value.trim();
      if(!raw){report.textContent='Paste the product information first.';return}
      const parsed=parseDetails(raw), changed=[];
      if(setField('product',parsed.product))changed.push('product');
      if(setField('model',parsed.model))changed.push('model');
      if(setField('description',parsed.description))changed.push('description');
      if(setField('features',parsed.features))changed.push('features');
      if(setField('applications',parsed.applications))changed.push('applications');
      if(setField('specs',parsed.specifications))changed.push('specification pairs');
      if(parsed.product && !$('q').value.trim())$('q').value=parsed.product;
      if($('editbadge'))$('editbadge').textContent='User-supplied details · review required';
      const count=(parsed.specifications.match(/\n/g)||[]).length+(parsed.specifications?1:0);
      report.textContent='Auto-filled: '+(changed.join(', ')||'none; existing edits retained')+
        '. '+count+' labelled technical specification pairs. Source: pasted/retrieved details (not manufacturer verified).'+
        (parsed.warnings.length?' Needs review: conflicting model(s) '+parsed.warnings.join(', ')+'.':'')+
        ' Use Generate with Gemini AI to improve the draft, or Generate Full Catalogue to preview the PDF.';
      report.className='notice '+(parsed.warnings.length?'error':'success');
    });
  }

  // Mini: functional grid and list presentation toggles.
  const miniRelated=$('mini-related');
  if(mini && miniRelated){
    const header=miniRelated.querySelector('.card-h');
    const toggle=node('div','view-toggle');
    for(const choice of ['Grid','List']){
      const btn=node('button','view-choice'+(choice==='Grid'?' active':''),choice);
      btn.type='button';
      btn.setAttribute('aria-pressed',String(choice==='Grid'));
      btn.addEventListener('click',()=>{
        miniRelated.classList.toggle('list-view',choice==='List');
        for(const b of toggle.querySelectorAll('button')){
          const yes=b.textContent===choice;
          b.classList.toggle('active',yes);
          b.setAttribute('aria-pressed',String(yes));
        }
      });
      toggle.append(btn);
    }
    header.append(toggle);
  }
  // Editable parameter-value editor: the textarea remains the canonical PDF input.
  const spec=$('specs');
  const editor=$('editor');
  if(!mini && spec && editor){
    const field=spec.closest('.field');
    const wrapper=node('div','spec-pairs-wrapper');
    const bar=node('div','spec-pairs-header');
    const heading=node('h3','','Technical Specification Pairs ');
    const counter=node('span','spec-count','(0)');
    heading.append(counter);
    const add=node('button','btn alt add-param','+ Add Parameter');
    add.type='button';
    bar.append(heading,add);
    const rows=node('div','spec-pairs');
    rows.id='spec-pairs';
    const pasteLabel=node('label','spec-paste-label','Paste specifications here — Ctrl + V');
    pasteLabel.htmlFor='spec-paste-box';
    const pasteArea=node('textarea','spec-paste-area');
    pasteArea.id='spec-paste-box';
    pasteArea.rows=5;
    pasteArea.spellcheck=false;
    pasteArea.placeholder='Paste a 2-column table or a list of specifications.\nExample: Brand: MOL\nModel: CS1000 / CS1500\nDetection principle: Infrared';
    pasteArea.setAttribute('aria-describedby','spec-paste-help spec-paste-feedback');
    const pasteHelp=node('p','spec-paste-help',
      'Instant import: paste with Ctrl + V. Supports copied Markdown tables, Excel / Google Sheets, Parameter: Value lines and alternating Specification / Details lists. Existing values stay unchanged.');
    pasteHelp.id='spec-paste-help';
    const pasteFeedback=node('div','spec-paste-feedback',
      'Ready to paste — imported entries will appear as editable rows below.');
    pasteFeedback.id='spec-paste-feedback';
    pasteFeedback.setAttribute('role','status');
    pasteFeedback.setAttribute('aria-live','polite');
    const technicalNotesPanel=node('section','full-spec-notes');
    technicalNotesPanel.id='full-technical-notes-panel';
    technicalNotesPanel.hidden=true;
    technicalNotesPanel.append(
      node('h4','full-spec-notes-title','TECHNICAL NOTES — additional source-aware context'));
    const technicalNotesText=node('p','full-spec-notes-copy','');
    technicalNotesText.id='full-technical-notes-text';
    technicalNotesPanel.append(technicalNotesText);
    wrapper.append(bar,pasteLabel,pasteArea,pasteHelp,pasteFeedback,rows,technicalNotesPanel);
    field.before(wrapper);
    const raw=document.createElement('details');
    raw.className='raw-spec-details';
    const summary=node('summary','','Edit raw specification text');
    raw.append(summary);
    field.before(raw);
    raw.append(field);
    let internal=false;
    const parse=()=>spec.value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean).map(line=>{
      const idx=line.indexOf(':');
      return idx<1?['Specification',line]:[line.slice(0,idx).trim(),line.slice(idx+1).trim()];
    }).slice(0,100);
    function pushRows(){
      internal=true;
      const values=[];
      for(const row of rows.querySelectorAll('.spec-row')){
        const k=row.querySelector('.spec-key').value.trim();
        const v=row.querySelector('.spec-value').value.trim();
        if(k&&v)values.push(k+': '+v);
      }
      spec.value=values.join('\n');
      spec.dispatchEvent(new Event('input',{bubbles:true}));
      internal=false;
      counter.textContent='('+values.length+')';
    }
    function addRow(key='',value=''){
      const row=node('div','spec-row');
      const k=node('input','spec-key');
      k.type='text';k.value=key;k.placeholder='Parameter e.g. Accuracy';k.maxLength=85;
      k.setAttribute('aria-label','Technical specification parameter');
      const v=node('input','spec-value');
      v.type='text';v.value=value;v.placeholder='Actual value from source';v.maxLength=400;
      v.setAttribute('aria-label','Technical specification value');
      const remove=node('button','remove-spec','×');
      remove.type='button';remove.title='Remove specification';
      remove.setAttribute('aria-label','Remove specification');
      remove.addEventListener('click',()=>{row.remove();pushRows()});
      k.addEventListener('input',pushRows);
      v.addEventListener('input',pushRows);
      row.append(k,v,remove);rows.append(row);
    }
    function refresh(){
      if(internal)return;
      rows.replaceChildren();
      for(const [k,v] of parse())addRow(k,v);
      counter.textContent='('+rows.querySelectorAll('.spec-row').length+')';
    }
    // Ctrl+V importer. Text remains text; no AI, API call or unsupported
    // technical facts are manufactured. Existing manually entered rows win.
    function importPaste(text){
      const parser=window.NUNESSpecPaste?.parse;
      if(typeof parser!=='function'){
        pasteFeedback.textContent='The paste reader did not load. Refresh the page and try again.';
        return false;
      }
      const result=parser(text);
      if(!result.recognized||!result.rows.length)return false;
      const existing=new Map();
      for(const row of rows.querySelectorAll('.spec-row')){
        const field=row.querySelector('.spec-key');
        const key=field?.value.trim().toLowerCase();
        if(key&&!existing.has(key))existing.set(key,row);
      }
      let added=0,filled=0,skipped=0;
      for(const [key,value] of result.rows){
        const norm=key.toLowerCase();
        const prior=existing.get(norm);
        if(prior){
          const destination=prior.querySelector('.spec-value');
          if(destination&&!destination.value.trim()){
            destination.value=value;
            filled++;
          }else skipped++;
          continue;
        }
        if(rows.querySelectorAll('.spec-row').length>=100){
          skipped++;continue;
        }
        addRow(key,value);
        existing.set(norm,rows.lastElementChild);
        added++;
      }
      if(added||filled)pushRows();
      pasteArea.value='';
      const total=(rows.querySelectorAll('.spec-row').length);
      pasteFeedback.textContent='Imported '+(added+filled)+' specification'+
        (added+filled===1?'':'s')+' instantly into the table.'+
        (skipped?' '+skipped+' duplicate/existing or over-limit row(s) kept unchanged.':'')+
        ' '+total+' editable row(s) shown. Review the source values before publishing.';
      pasteFeedback.classList.toggle('has-imported',Boolean(added||filled));
      return true;
    }
    pasteArea.addEventListener('paste',event=>{
      const text=event.clipboardData?.getData('text/plain')||'';
      if(text&&importPaste(text)){
        event.preventDefault(); // no duplicate raw text in the import box
      }
    });
    // The general "Paste Product Details" box is also a direct target for
    // pasted 2-column specification tables. For table-only input, import
    // straight into Technical Specification Pairs and show the results.
    const detailsPaste=$('pasted-details');
    if(detailsPaste){
      detailsPaste.addEventListener('paste',event=>{
        const text=event.clipboardData?.getData('text/plain')||'';
        if(!text.trim())return;
        const parser=window.NUNESSpecPaste?.parse;
        if(typeof parser!=='function')return;
        const parsed=parser(text);
        const isTable=parsed.recognized&&parsed.rows.length>0&&(
          /(?:^|\n)\s*\|[\s\S]*\|\s*(?:\n|$)/.test(text)||
          /(?:^|\n)\s*(?:Specification|Parameter)\s*\n\s*(?:Details|Value)\s*(?:\n|$)/i.test(text)||
          /(?:^|\n)\s*(?:Specification|Parameter)\s*\t\s*(?:Details|Value)/i.test(text)
        );
        if(!isTable)return; // Keep full mixed product briefs in the normal importer.
        if(importPaste(text)){
          event.preventDefault();
          const report=$('autofill-report');
          if(report){
            report.textContent=parsed.rows.length+
              ' specification pairs pasted directly into the editable table. '+
              'Check the Specifications section; existing rows were preserved.';
            report.className='notice success';
          }
          wrapper.scrollIntoView({behavior:'smooth',block:'nearest'});
        }
      });
    }
    // Also supports mobile Paste and browsers without clipboardData support.
    pasteArea.addEventListener('input',()=>{
      const text=pasteArea.value;
      if(!text.trim())return;
      if(importPaste(text))return;
      if(text.includes('\n')||text.includes('\t')||text.includes('|')){
        pasteFeedback.classList.remove('has-imported');
        pasteFeedback.textContent='Could not identify a complete two-column table yet. '+
          'Try "Brand: MOL" lines or include Specification / Details column headers.';
      }
    });
    // A multirow clipboard pasted into either editable Parameter/Value cell
    // imports the entire table rather than filling one cell with broken text.
    rows.addEventListener('paste',event=>{
      if(!event.target.closest('.spec-row'))return;
      const text=event.clipboardData?.getData('text/plain')||'';
      if(!/[\n\t|]/.test(text))return;
      if(importPaste(text))event.preventDefault();
    });
    // The previous expandable raw-text editor also supports table imports.
    spec.addEventListener('paste',event=>{
      const text=event.clipboardData?.getData('text/plain')||'';
      if(!/[\n\t|]/.test(text))return;
      if(importPaste(text))event.preventDefault();
    });
    add.addEventListener('click',()=>{addRow();rows.lastElementChild?.querySelector('input')?.focus();});
    spec.addEventListener('input',()=>{
      refresh();
      // Notes are derived from specific real parameter/value rows.
      // Invalidate them as soon as any editor row changes.
      technicalNotesPanel.hidden=true;
      technicalNotesText.textContent='';
      document.dispatchEvent(new Event('nunes:technical-notes-updated'));
    });
    refresh();
    // Flexible section tabs keep the existing underlying inputs and behavior.
    const body=editor.querySelector('.body');
    const tabs=node('div','editor-tabs');
    const fields={
      'Specifications':wrapper,
      'Description & Features':$('description').closest('.field'),
      'Titles & Meta':$('product').closest('.formgrid')
    };
    for(const [name,element] of Object.entries(fields)){
      const tab=node('button','editor-tab',name);
      tab.type='button';
      tab.addEventListener('click',()=>{
        tabs.querySelectorAll('button').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-selected','false');});
        tab.classList.add('active');tab.setAttribute('aria-selected','true');
        const destination=element;
        destination.scrollIntoView({behavior:'smooth',block:'start'});
        destination.classList.add('tab-target');
        setTimeout(()=>destination.classList.remove('tab-target'),1400);
      });
      tab.setAttribute('role','tab');
      tab.setAttribute('aria-selected','false');
      tabs.append(tab);
    }
    tabs.firstChild.classList.add('active');
    tabs.firstChild.setAttribute('aria-selected','true');
    tabs.setAttribute('role','tablist');
    body.prepend(tabs);
    const rule=node('p','accuracy-rule','Accuracy rule: use only supplied or source-backed technical details. Review values before exporting.');
    wrapper.after(rule);
  }
  // Actual PDF navigation: all pages or any individual page. Mini often
  // has three or more sheets; previous UI stopped at Page 2.
  const previewCard=$('preview-card');
  if(previewCard){
    const body=previewCard.querySelector('.body');
    const bar=node('div','pdf-controls');
    const group=node('div','pdf-pages');
    const all=node('button','page-choice active','All Pages');
    all.type='button';all.disabled=true;
    all.setAttribute('aria-pressed','true');
    const prev=node('button','page-choice','Previous');
    prev.type='button';prev.disabled=true;
    const select=node('select','mini-page-selector');
    select.setAttribute('aria-label','Choose a PDF preview page');
    select.disabled=true;
    const next=node('button','page-choice','Next');
    next.type='button';next.disabled=true;
    const zoom=node('select','zoom-select');
    zoom.setAttribute('aria-label','PDF preview zoom');
    for(const [value,label] of [['fit','Fit'],['55','55%'],['75','75%'],['100','100%']]){
      const option=node('option','',label);option.value=value;zoom.append(option);
    }
    let page=0,pageCount=0;
    function updateControls(){
      const ready=Boolean(pdfUrl)&&pageCount>0;
      all.disabled=!ready;
      prev.disabled=!ready||page<=1;
      next.disabled=!ready||page>=pageCount;
      select.disabled=!ready;
      all.classList.toggle('active',page===0);
      all.setAttribute('aria-pressed',String(page===0));
      if(page>0)select.value=String(page);
      counter.textContent=ready
        ?(page===0?'Preview: All '+pageCount+' pages':'Preview: Page '+page+' of '+pageCount)
        :'Preview: no PDF';
    }
    function renderPdf(){
      const frame=$('preview')?.querySelector('iframe');
      if(!frame||!pdfUrl)return;
      const z=zoom.value==='fit'?'page-width':zoom.value;
      frame.src=pdfUrl+'#toolbar=1&navpanes=0'+
        (page>0?'&page='+page:'')+'&zoom='+z;
      updateControls();
    }
    const counter=node('span','page-counter','Preview: no PDF');
    all.onclick=()=>{page=0;renderPdf()};
    prev.onclick=()=>{if(page>1){page--;renderPdf()}};
    next.onclick=()=>{if(page<pageCount){page=page===0?1:page+1;renderPdf()}};
    select.onchange=()=>{const selected=Number(select.value);if(selected>=1&&selected<=pageCount){page=selected;renderPdf()}};
    zoom.onchange=renderPdf;
    group.append(all,prev,select,next);
    bar.append(group,zoom,counter);
    body.prepend(bar);
    window.nunesPdfPreviewUpdated=(count)=>{
      pageCount=Math.min(100,Math.max(0,Number(count)||0));
      page=0;select.replaceChildren();
      for(let i=1;i<=pageCount;i++){
        const option=node('option','', 'Page '+i+' of '+pageCount);
        option.value=String(i);select.append(option);
      }
      renderPdf();
      updateControls();
    };
    updateControls();
  }
  const footer=document.querySelector('.footer');
  if(footer)footer.textContent='© Nunes Instrumentation · Catalogue Studio · Review source details before publishing';
})();
