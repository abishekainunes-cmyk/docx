/* Live, editable reference-format output for the NUNES Full Catalogue.
 * All displayed content comes from the canonical editor fields; no sample
 * technical specifications are fabricated to populate the preview. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const root=$('reference-content-review');
if(!root||location.pathname==='/mini-catalogue')return;
const panel=$('reference-content-body');
const button=$('copy-reference-content');
const lines=id=>($(id)?.value||'').split(/\r?\n/).map(x=>x.trim().replace(/^[-*•]\s*/,'')).filter(Boolean);
const append=(tag,parent,words,className)=>{
 const el=document.createElement(tag);el.textContent=words;
 if(className)el.className=className;
 parent.append(el);return el;
};
const toPairs=()=>{
 const found=[],seen=new Set();
 for(const row of lines('specs')){
   const colon=row.indexOf(':');
   if(colon<1)continue;
   const name=row.slice(0,colon).trim(),value=row.slice(colon+1).trim();
   if(!name||!value||seen.has(name.toLowerCase()))continue;
   seen.add(name.toLowerCase());found.push([name,value]);
 }
 // The preview must show exactly the rows submitted to the PDF.
 // Do not invent a fifth "Model" row just because Model Number is filled.
 return found;
};
// The preview mirrors the server's preference for concrete technical
// values, and does not invent a fifth row or an eighth key feature.
const contextKeys=new Set([
 'instrument type','test category','typical operating context','intended function',
 'measurement function','application category','technical configuration',
 'typical sample type','method category','detection medium',
 'analysis principle'
]);
const unusable=/verification required|pending confirmation|not specified|exact-model datasheet|product category identified|product purpose as identified|manufacturer model details|not verified|to be confirmed|confirm for exact model|model details require confirmation|datasheet confirmation|laboratory or industrial instrumentation|not supplied/i;
function referenceRowsForPDF(rows){
 return rows.map(([key,value],i)=>({key,value,i,
     priority:contextKeys.has(key.toLowerCase())?1:0}))
   .filter(row=>!unusable.test(row.value))
   .sort((a,b)=>a.priority-b.priority||a.i-b.i)
   .slice(0,8).map(row=>[row.key,row.value]);
}
function prepared(){
 const product=$('product')?.value.trim()||'';
 const model=$('model')?.value.trim()||'';
 const heading=product+(model&&!product.toLowerCase().includes(model.toLowerCase())?' – Model '+model:'');
 const description=$('description')?.value.trim()||'';
 const rawSpecs=toPairs();
 return {product,model,heading,description,rawSpecs,
   features:[...new Set(lines('features'))].slice(0,10),
   specs:referenceRowsForPDF(rawSpecs),applications:lines('applications'),
   technicalNotes:$('full-technical-notes-text')?.textContent.trim()||''};
}
function formatted(data){
 const out=['**'+data.heading+'**','','**PRODUCT SPECIFICATION**',''];
 out.push(...(data.specs.length?data.specs.map(([k,v])=>'- '+k+': '+v):['(Provide source-backed product specifications)']));
 if(data.technicalNotes)out.push('','**TECHNICAL NOTES**','',data.technicalNotes);
 out.push('','**PRODUCT DESCRIPTION**','',data.description,'','**Key Features**','');
 out.push(...(data.features.length?data.features.map(x=>'- '+x):['(Prepare 8–10 product-relevant key-feature lines)']));
 return out.join('\n');
}
function render(){
 const data=prepared();
 panel.replaceChildren();
 const stats=$('reference-content-stats');
 if(!data.product){
   if(stats)stats.textContent='Description: 0 words · Features: 0 · Specifications: 0';

   append('p',panel,'Search a product or enter its details to preview the full reference-format content.','reference-empty');
   button.disabled=true;
   return;
 }
 button.disabled=false;
 const words=(data.description.match(/[\p{L}\p{N}]+(?:[-/][\p{L}\p{N}]+)*/gu)||[]).length;
 const statsReady=words>=150&&words<=200&&data.features.length>=8&&data.features.length<=10&&data.specs.length>=1;
 const count=data.rawSpecs.length;
 const featureWords=(data.features.join(' ').match(/[\p{L}\p{N}]+(?:[-/][\p{L}\p{N}]+)*/gu)||[]).length;
 const notesWords=(data.technicalNotes.match(/[\p{L}\p{N}]+(?:[-/][\p{L}\p{N}]+)*/gu)||[]).length;
 const counts='Description: '+words+'/150–200 words · Key Features: '+featureWords+
   ' words across '+data.features.length+'/8–10 lines · Specifications: '+
   data.specs.length+(count>8?' selected from '+count:'')+
   ' · Technical Notes: '+notesWords+' words';
 if(stats){
   stats.textContent=counts+(statsReady
     ?' · Content can be exported without ticking a checkbox.'
     :' · Provide a meaningful description, a key feature and at least one real technical value.');
   stats.style.color=statsReady?'#166534':'#a16207';
 }
 append('h3',panel,'PAGE 1 — '+data.heading,'reference-title');
 function section(title,items){
   append('h4',panel,title,'reference-heading');
   if(!items.length){append('p',panel,'Not supplied — review required.','reference-empty');return;}
   const list=append('ul',panel,'','reference-list');
   for(const item of items)append('li',list,item);
 }
 section('PRODUCT SPECIFICATION — '+data.specs.length+' supplied row(s)',data.specs.map(([k,v])=>k+': '+v));
 if(data.technicalNotes){
   append('h4',panel,'TECHNICAL NOTES — '+notesWords+' words','reference-heading');
   append('p',panel,data.technicalNotes,'reference-paragraph');
 }
 append('h3',panel,'PAGE 2','reference-title');
 append('h4',panel,'PRODUCT DESCRIPTION','reference-heading');
 if(!data.description)append('p',panel,'Add a product description; 60–80 words is recommended.','reference-empty');
 else append('p',panel,data.description.replace(/\s+/g,' ').trim(),'reference-paragraph');
 section('Key Features — '+data.features.length+' supplied item(s)',data.features);
 append('p',panel,'NUNES office and service footer: original artwork retained in the PDF.','reference-empty');
}
button.addEventListener('click',async()=>{
 const data=prepared();
 if(!data.product)return;
 const copy=formatted(data);
 try{
   await navigator.clipboard.writeText(copy);
   button.textContent='Copied formatted catalogue content';
   setTimeout(()=>{button.textContent='Copy Formatted Content';},2200);
 }catch(e){
   const pad=document.createElement('textarea');
   pad.value=copy;pad.style.cssText='position:fixed;left:-9999px;top:-9999px';
   document.body.append(pad);pad.select();
   try{document.execCommand('copy');button.textContent='Copied formatted catalogue content';}
   finally{pad.remove();setTimeout(()=>{button.textContent='Copy Formatted Content';},2200);}
 }
});
document.addEventListener('input',evt=>{
 if(['product','model','specs','description','features','applications'].includes(evt.target?.id))render();
});
document.addEventListener('nunes:technical-notes-updated',render);
document.addEventListener('change',render);
render();
})();