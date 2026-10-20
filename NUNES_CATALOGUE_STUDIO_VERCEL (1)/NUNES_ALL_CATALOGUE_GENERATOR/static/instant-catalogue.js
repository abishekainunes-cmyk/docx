/* Cloud-only, user-initiated NUNES instant Full + Mini catalogue.
 * Works in the existing website without a Windows local listener.
 * Public IndiaMART source research only; seller sessions remain local.
 * Generates review-draft Full PDFs when exact technical evidence is missing.
 */
(()=>{
"use strict";
const byId=id=>document.getElementById(id);
const start=byId("instant-cloud-build");
if(!start)return;
const status=byId("instant-cloud-status"),results=byId("instant-cloud-results");
const keptUrls=[];
let running=false;

function report(message,kind=""){
 status.textContent=message;
 status.dataset.state=kind;
}
function clean(v){return String(v||"").replace(/\s+/g," ").trim()}
function exactSource(v,limit=500){
 try{
  const url=new URL(String(v||""));
  return url.protocol==="https:"?url.href.slice(0,limit):"";
 }catch(_){return ""}
}
function sanitize(row){
 if(!row||typeof row!=="object")return null;
 const product=clean(row.product||row.name).slice(0,130);
 if(product.length<5)return null;
 const image_link=exactSource(row.image_link||"",1500);
 return {
  product,model:clean(row.model||"").slice(0,65),
  source_url:exactSource(row.source_url),image_link,
  source:clean(row.source||"Public product evidence").slice(0,100)
 };
}
function unique(rows){
 const out=[],seen=new Set();
 for(const raw of rows||[]){
  const row=sanitize(raw);
  if(!row)continue;
  // One catalogue record per actual product name and source listing.
  const key=row.product.toLowerCase()+"|"+row.source_url;
  if(seen.has(key))continue;
  seen.add(key);out.push(row);
  if(out.length===8)break;
 }
 return out;
}
function galleryItems(){
 return [...document.querySelectorAll("#source-links .nunes-gallery-card")].map(card=>({
  product:card.dataset.productName||card.querySelector(".nunes-gallery-name")?.textContent||"",
  image_link:card.dataset.imageLink||"",
  source_url:card.dataset.sourceUrl||"",
  source:card.dataset.photoSource||"Public image search"
 }));
}
function visibleCandidates(query){
 const active=clean(query).toLowerCase();
 const sourceRoot=byId("source-links");
 if(sourceRoot?.dataset.query?.trim().toLowerCase()===active){
  const photos=unique(galleryItems());
  if(photos.length)return photos;
  if(typeof fullEvidenceProducts!=="undefined"){
   const full=unique(fullEvidenceProducts);
   if(full.length)return full;
  }
 }
 const categories=byId("mini-categories");
 if(categories?.dataset.query?.trim().toLowerCase()===active &&
    typeof miniProducts!=="undefined"){
  const choices=unique(miniProducts.filter(p=>p.selected));
  if(choices.length)return choices;
 }
 return [];
}
async function checkResponse(response,label,expectedType){
 if(!response.ok){
  const details=await response.json().catch(()=>({}));
  throw Error((details.error||label+" failed")+
    " (HTTP "+response.status+")");
 }
 const blob=await response.blob();
 if(blob.size<100 || (expectedType==="pdf" && !blob.type.includes("pdf"))){
  throw Error(label+" returned an invalid or empty "+expectedType.toUpperCase());
 }
 if(expectedType==="zip"){
  const header=new Uint8Array(await blob.slice(0,4).arrayBuffer());
  if(header[0]!==80||header[1]!==75)
   throw Error(label+" did not return a ZIP archive.");
 }
 return blob;
}
function timeoutSignal(){
 return typeof AbortSignal!=="undefined"&&typeof AbortSignal.timeout==="function"?
  AbortSignal.timeout(115000):undefined;
}
function addLink(blob,name,label){
 const url=URL.createObjectURL(blob);
 keptUrls.push(url);
 const a=document.createElement("a");
 a.href=url;a.download=name;a.className="instant-cloud-file";
 a.textContent=label;
 a.setAttribute("aria-label","Download "+label);
 results.append(a);
 return url;
}
function showMiniPreview(url,pages){
 const preview=byId("preview"),kind=byId("previewtype");
 if(!preview)return;
 // All browser URLs are owned by this control; never revoke a previous
 // user's download before they have downloaded the generated file.
 if(typeof pdfUrl!=="undefined")pdfUrl=url;
 if(typeof pdfName!=="undefined")pdfName="NUNES_Instant_Mini_Catalogue.pdf";
 const frame=document.createElement("iframe");
 frame.src=url+"#toolbar=1&view=FitH";
 frame.title="Generated NUNES instant Mini Catalogue";
 preview.replaceChildren(frame);
 if(kind)kind.textContent="Instant Mini Catalogue · PDF ready";
 const download=byId("download"),open=byId("zoomin");
 if(download)download.disabled=false;
 if(open)open.disabled=false;
 if(typeof window.nunesPdfPreviewUpdated==="function"){
  window.nunesPdfPreviewUpdated(Number(pages)||0);
 }
}
async function research(query){
 // Existing public research populates Source Evidence as well as returning
 // attributed product photos. No IndiaMART seller-login access is attempted.
 let info=null;
 if(typeof retrieveProductSources==="function")
  info=await retrieveProductSources(query,"");
 // Some public sources expose a product photograph but no readable
 // numerical specifications. Preserve the displayed photo choices as
 // REVIEW-draft candidates even when the research endpoint returns
 // found=false and the UI's helper returns null.
 const visible=visibleCandidates(query);
 if(visible.length)return visible;
 let photos=unique(info?.image_candidates||[]);
 if(photos.length)return photos;
 // Fall back to source-linked public product listings, preserving unmatched
 // names as names-only entries in the Mini PDF.
 report("Checking public IndiaMART product listings for "+query+"…");
 try{
  const response=await fetch("/api/mini/related?q="+encodeURIComponent(query),{
   cache:"no-store",signal:timeoutSignal()
  });
  if(response.ok){
   const data=await response.json();
   return unique((data.categories||[]).flatMap(group=>group.products||[]));
  }
 }catch(_){}
 return [];
}
async function instant(){
 if(running)return;
 const query=clean(byId("q")?.value||byId("product")?.value);
 if(query.length<4){
  report("Enter a product name or category first, then click Build Full + Mini PDFs.","error");
  byId("q")?.focus();
  return;
 }
 running=true;start.disabled=true;
 results.replaceChildren();
 let candidates=[];
 try{
  report("Step 1/3: Preparing public product evidence for "+query+"…","busy");
  candidates=visibleCandidates(query);
  if(!candidates.length)candidates=await research(query);
  if(!candidates.length){
   // Operator's name only: produce clearly labelled review drafts, not fake
   // search hits or unverified performance specifications.
   candidates=[{product:query,model:"",source_url:"",image_link:"",
    source:"User-entered name; no external source matched"}];
  }
  const withPhoto=candidates.filter(p=>Boolean(p.image_link)).length;
  report("Step 2/3: Found "+candidates.length+" item(s), "+withPhoto+
   " source photo(s). Building Full ZIP and combined Mini PDF in parallel…","busy");
  const focus=candidates[0];
  const miniData={
   type:"mini",product:focus.product,model:focus.model||"",
   image_link:focus.image_link||"",related:candidates.slice(1),
   keywords:candidates.map(p=>p.product).join(", ")
  };
  // Respect the same NUNES private Drive save code as the manual PDF
  // export. A public visitor can never upload anonymously.
  const headers={"Content-Type":"application/json","X-Nunes-AI-Request":"1"};
  if(typeof window.addDriveBatchHeaders==="function")
    window.addDriveBatchHeaders(headers); // may request owner code, or stop
  const wantsDrive=headers["X-Nunes-Drive-Save"]==="1";
  const fullRequest=fetch("/api/catalogue/full-batch",{
   method:"POST",cache:"no-store",signal:timeoutSignal(),
   headers:{...headers},body:JSON.stringify({products:candidates})
  }).then(async response=>({response,blob:await checkResponse(response,"Full catalogue batch","zip")}));
  const miniRequest=fetch("/api/generate",{
   method:"POST",cache:"no-store",signal:timeoutSignal(),
   headers:{...headers},body:JSON.stringify(miniData)
  }).then(async response=>({response,blob:await checkResponse(response,"Mini catalogue","pdf")}));
  const [full,mini]=await Promise.allSettled([fullRequest,miniRequest]);
  let successes=0,issues=[],savedFull=0,savedMini=0;
  if(full.status==="fulfilled"){
   const {blob,response}=full.value;
   if(wantsDrive){
     const state=typeof window.showBatchDriveStatus==="function"
       ?window.showBatchDriveStatus(response,"Instant Full Catalogue batch"):{status:""};
     savedFull=Number(state.saved||0);
     if(state.status!=="saved")
       issues.push("Full Drive save: "+(state.status||"no confirmation from server"));
   }
   addLink(blob,"NUNES_Instant_Full_Catalogues.zip",
     "Download Full Catalogues ZIP ("+
     (response.headers.get("X-Nunes-Batch-Total")||String(candidates.length))+" PDFs)");
   const draftCount=Number(response.headers.get("X-Nunes-Batch-Review-Drafts")||0);
   if(draftCount){
    const note=document.createElement("small");
    note.className="instant-cloud-note";
    note.textContent=draftCount+" Full PDF(s) require technical source review. See BATCH_REPORT.csv inside ZIP.";
    results.append(note);
   }
   successes++;
  }else issues.push("Full ZIP: "+String(full.reason?.message||full.reason));
  if(mini.status==="fulfilled"){
   const {blob,response}=mini.value;
   if(wantsDrive){
     const saveState=response.headers.get("X-Nunes-Drive-Status")||"no confirmation";
     savedMini=saveState==="saved"?1:0;
     if(savedMini){
       if(typeof window.setNotice==="function")
         window.setNotice("drive-status","Instant Mini PDF was saved to the configured Mini Catalogue folder.", "success");
     }else{
       issues.push("Mini Drive save: "+saveState);
       if(typeof window.setNotice==="function")
         window.setNotice("drive-status","The Mini PDF was generated but not saved to Drive ("+saveState+"). Check the company code and folder access.","error");
     }
   }
   const file=addLink(blob,"NUNES_Instant_Mini_Catalogue.pdf",
     "Download Combined Mini Catalogue PDF");
   showMiniPreview(file,response.headers.get("X-Nunes-Page-Count"));
   successes++;
  }else issues.push("Mini PDF: "+String(mini.reason?.message||mini.reason));
  if(successes){
   report("Step 3/3: "+successes+" of 2 downloads ready. "+candidates.length+
    " public-source or user-entered product(s) processed. "+
    (wantsDrive?(savedFull+savedMini)+" individual PDF(s) saved to Google Drive. ":"Google Drive saving was not selected. ")+
    "Review all technical details before publishing."+
    (issues.length?" Needs attention: "+issues.join("; "):""),issues.length?"warning":"success");
  }else throw Error(issues.join("; ")||"Both PDF operations failed");
 }catch(error){
  report("Instant workflow needs attention: "+String(error.message||error),"error");
 }finally{
  running=false;start.disabled=false;
 }
}
start.addEventListener("click",instant);
})();
