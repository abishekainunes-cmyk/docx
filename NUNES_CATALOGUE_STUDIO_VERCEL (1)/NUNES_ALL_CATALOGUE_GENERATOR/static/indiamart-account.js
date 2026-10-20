/* IndiaMART owner-account export importer.
 * File is parsed in the operator's browser; no credentials, cookies or
 * seller-session information are uploaded to the server.
 * The server gets only product-source rows when a batch is explicitly run.
 */
(()=>{
"use strict";
const $=id=>document.getElementById(id);
if(!$("account-export-file"))return;
const input=$("account-export-file");
const alias=$("account-alias");
const load=$("account-load-next");
const reset=$("account-reset");
const status=$("account-import-status");
const note=$("account-batch-note");
let records=[],processed={},currentBatch=[];
function canonical(value){return String(value||"").toLowerCase().replace(/\s+/g," ").trim();}
function header(value){return canonical(value).replace(/[^a-z0-9]+/g," ");}
const aliases={
 product:["product name","product","item name","item","product service name","name","title","itemname","product title"],
 model:["model","model no","model number","model name","product model","source model"],
 brand:["brand","brand name","manufacturer","make","original brand","source brand"],
 source_url:["product url","product link","source url","listing url","indiamart url","product detail url","url","link"],
 source_id:["product id","item id","product code","product service code","sku","id","source id"],
 image_link:["image url","photo url","image link","image_link","product image"],
 description:["description","product description","details"],
 specifications:["specifications","technical specifications","specs"]
};
function sourceUrl(value){
 try{
  const url=new URL(String(value||"").trim());
  if(url.protocol!=="https:"||!/(^|\.)indiamart\.com$/i.test(url.hostname))return "";
  if(!/\/(?:proddetail|product)\//i.test(url.pathname))return "";
  return url.href.slice(0,500);
 }catch(_){return ""}
}
function normalizeRow(row){
 if(!row||typeof row!=="object"||Array.isArray(row))return null;
 const lower={};
 for(const [k,v] of Object.entries(row))lower[header(k)]=v;
 const field=name=>{
  for(const key of aliases[name]){
   const value=lower[header(key)];
   if(value!==null&&value!==undefined&&String(value).trim())return String(value).trim();
  }
  return "";
 };
 const product=field("product").replace(/\s+/g," ").slice(0,170);
 if(product.length<4)return null;
 const model=field("model").replace(/\s+/g," ").slice(0,100);
 const url=sourceUrl(field("source_url"));
 const brand=field("brand").slice(0,120);
 const source_id=field("source_id").slice(0,120)||
      canonical(product)+"|"+canonical(model);
 return {
   product,model,source_model:model,source_brand:brand,
   source_id,source_url:url,
   image_link:field("image_link").slice(0,1500),
   description:field("description").slice(0,3700),
   specifications:field("specifications").slice(0,5800),
   status:"captured",catalogue_brand:"VTech",catalogue_model:"VT"
 };
}
function parseCSV(raw){
 // RFC-4180 fields: quoted comma, embedded newline and double quotes.
 const text=String(raw||"").replace(/^\uFEFF/,"");
 const first=(text.split(/\r?\n/,1)[0]||"");
 const candidates=[",",";","\t"];
 const delimiter=candidates.reduce((best,c)=>first.split(c).length>first.split(best).length?c:best,",");
 let rows=[],row=[],field="",quoted=false;
 for(let i=0;i<text.length;i++){
  const ch=text[i];
  if(quoted){
   if(ch==='"'&&text[i+1]==='"'){field+='"';i++;}
   else if(ch==='"')quoted=false;
   else field+=ch;
  }else if(ch==='"')quoted=true;
  else if(ch===delimiter){row.push(field);field="";}
  else if(ch==="\n"){
   row.push(field.replace(/\r$/,""));field="";
   if(row.some(x=>String(x).trim()))rows.push(row);
   row=[];
  }else field+=ch;
 }
 if(field||row.length){row.push(field.replace(/\r$/,""));rows.push(row)}
 if(rows.length<2)return [];
 const columns=rows.shift().map(x=>String(x).trim());
 return rows.map(values=>Object.fromEntries(columns.map((c,i)=>[c,values[i]||""])));
}
function checksum(value){
 // Anonymized storage fingerprint; no seller product descriptions stored.
 let h=2166136261;
 for(let i=0;i<value.length;i++){h^=value.charCodeAt(i);h=Math.imul(h,16777619)}
 return (h>>>0).toString(16).padStart(8,"0");
}
function rowKey(row){return checksum(row.source_id+"|"+canonical(row.product)+"|"+canonical(row.model))}
function version(row){
 return checksum([row.product,row.model,row.source_brand,row.source_url,
   row.image_link,row.description,row.specifications].join("\u001f"));
}
function storageKey(){return "nunes_indiamart_import_v1_"+checksum(canonical(alias.value)||"account1")}
function saveProgress(){
 try{localStorage.setItem(storageKey(),JSON.stringify(processed))}catch(_){}
}
function restore(){
 try{
  const saved=JSON.parse(localStorage.getItem(storageKey())||"{}");
  processed=saved&&typeof saved==="object"&&!Array.isArray(saved)?saved:{};
 }catch(_){processed={}}
}
function remaining(){return records.filter(row=>processed[rowKey(row)]!==version(row))}
function display(){
 const rem=remaining();
 $("account-total").textContent=String(records.length);
 $("account-remaining").textContent=String(rem.length);
 $("account-completed").textContent=String(records.length-rem.length);
 load.disabled=!rem.length;
 reset.disabled=!records.length;
}
function info(text,success=false){
 status.textContent=text;status.className="notice"+(success?" success":"");
}
input.addEventListener("change",async()=>{
 const file=input.files?.[0];if(!file)return;
 if(file.size>16_000_000){
  info("Export is over 16 MB. Split the seller products file into smaller exports.");return;
 }
 try{
  const raw=await file.text();
  let data=file.name.toLowerCase().endsWith(".json")||raw.trimStart().startsWith("{")||raw.trimStart().startsWith("[")
    ?JSON.parse(raw):parseCSV(raw);
  if(data&&!Array.isArray(data))data=data.products||data.items||data.records||[];
  if(!Array.isArray(data))throw Error("Expected CSV table or JSON products array");
  if(data.length>10000)throw Error("File exceeds 10,000 rows. Split into multiple exports.");
  const seen=new Set();
  records=[];
  for(const source of data){
   const row=normalizeRow(source);
   if(!row)continue;
   const id=rowKey(row);
   if(seen.has(id))continue;
   seen.add(id);records.push(row);
  }
  if(!records.length)throw Error("No valid product name column found. Export IndiaMART products CSV with a Product Name or Item Name column.");
  restore();currentBatch=[];display();
  info("Imported "+records.length+" owner-supplied products. "+
    remaining().length+" new or changed since the last completed browser batch. "+
    "Original manufacturer and source model are retained; catalogue branding defaults to VTech / VT.",true);
  note.textContent="Click Load Next 20 to prepare the website's batch workspace. The desktop Windows sync script is better for running all "+records.length+" products unattended.";
 }catch(error){
  records=[];currentBatch=[];processed={};display();
  info("Import failed: "+error.message);
 }
});
alias.addEventListener("change",()=>{if(records.length){restore();display();}});
load.addEventListener("click",()=>{
 const pending=remaining();
 if(!pending.length){info("All products from this export have been processed successfully.",true);return}
 currentBatch=pending.slice(0,20);
 $("batch-products").value=currentBatch.map(row=>
   row.product+(row.source_url?" | "+row.source_url:"")).join("\n");
 if(typeof window.nunesBatchLoadSources==="function")
   window.nunesBatchLoadSources(currentBatch);
 note.textContent="Loaded "+currentBatch.length+" products into Product List Automation below. "+
   "Select Full and Mini PDF, then click Start Product List Automation. "+
   "When completed, load the next 20; unfinished products stay pending.";
 $("batch-workflow").scrollIntoView({behavior:"smooth",block:"start"});
 info("Batch ready: "+currentBatch.length+" of "+pending.length+" remaining products.",true);
});
reset.addEventListener("click",()=>{
 if(!records.length)return;
 if(!window.confirm("Reset this account's browser checkpoint? Previously generated PDF files are not deleted."))return;
 processed={};saveProgress();display();
 info("Sync checkpoint reset. All imported products are available to process again.",true);
});
window.addEventListener("nunes:account-batch-finished",event=>{
 const completed=event.detail?.completed||[];
 if(!Array.isArray(completed)||!records.length)return;
 const names=new Set(completed.map(canonical));
 for(const row of currentBatch){
  if(names.has(canonical(row.product)))processed[rowKey(row)]=version(row);
 }
 saveProgress();display();
 info("Batch completed: "+completed.length+" source-ready product PDF(s). "+
   remaining().length+" new, changed, or evidence-incomplete item(s) remain. "+
   "Use the Windows runner for unattended all-product sync.",true);
});

// Inspect ONLY the non-sensitive, local 127.0.0.1 health endpoint.
// The hosted page cannot read IndiaMART login cookies or query Chrome tabs.
const localCheck=$("seller-check-local");
if(localCheck){
  const liveStatus=$("seller-live-status");
  const liveDetail=$("seller-live-detail");
  const lastScan=$("seller-last-scan");
  const output=$("seller-live-output");
  const clock=x=>{
    if(!x)return "Not verified";
    const when=new Date(x);
    return Number.isNaN(when.getTime())?"Not verified":when.toLocaleString();
  };
  async function checkLocal(){
    localCheck.disabled=true;
    liveStatus.textContent="Checking Windows connector…";
    try{
      const response=await fetch("http://127.0.0.1:8765/health",{
        method:"GET",mode:"cors",cache:"no-store",
        signal:AbortSignal.timeout(4500)
      });
      if(!response.ok)throw Error("Local connector replied with HTTP "+response.status);
      const state=await response.json();
      if(state.receiver!=="running")throw Error("Unknown local receiver response");
      const totals=state.pdf_counts||{};
      $("seller-live-total").textContent=String(state.captured_products||0);
      $("seller-live-full").textContent=String(totals.full_created||0);
      $("seller-live-mini").textContent=String(totals.mini_created||0);
      $("seller-live-review").textContent=String(totals.needs_review||0);
      lastScan.textContent=clock(state.last_successful_scan);
      output.textContent=state.output_folder||"Check BAT window";
      let status="Local Runner Ready",detail="Windows receiver online; waiting for extension pairing and an authorized seller scan.";
      if(state.extension_paired){
        status="Extension Paired";
        detail="Local Chrome extension authenticated. Open your seller Manage Products tab and scan.";
      }
      if(state.pdf_state==="scanning"){
        status="Scanning";
        detail="Current scan: "+(state.pages_scanned||0)+" page(s), "+
          (state.captured_products||0)+" captured product(s).";
      }else if(state.pdf_state==="queued"||state.pdf_state==="generating"){
        status="Generating PDFs";
        detail="An authorized product capture was received; the Windows runner is preparing catalogues.";
      }else if(state.pdf_state==="finished"&&state.account_connected){
        status="Completed";
        detail="A real authorized product scan completed and the PDF workflow finished. Review the local report for source-data gaps.";
      }else if(state.pdf_state==="error"){
        status="Needs Attention";
        detail="The local runner reports a PDF or scan error; review its Windows terminal and Catalogues/last-report.json.";
      }else if(state.account_connected){
        status="Seller Page Detected";
        detail="A real seller-page scan returned "+(state.captured_products||0)+" product(s); only safe product data was captured.";
      }
      liveStatus.textContent=status;
      liveDetail.textContent=detail;
    }catch(error){
      liveStatus.textContent="Disconnected / status unavailable";
      liveDetail.textContent="No verified connection to the local Windows receiver. "+
        "Start the BAT; check the extension popup. Some browsers block a website-to-localhost status request.";
      $("seller-live-total").textContent="—";
      $("seller-live-full").textContent="—";
      $("seller-live-mini").textContent="—";
      $("seller-live-review").textContent="—";
    }finally{
      localCheck.disabled=false;
    }
  }
  localCheck.addEventListener("click",checkLocal);
  // Fresh status is only an indication; the extension's scan is the source
  // of truth. Poll unobtrusively while the tab is visible.
  checkLocal();
  setInterval(()=>{if(!document.hidden&&!localCheck.disabled)checkLocal()},30000);
}

})();
