/* NUNES: human-initiated, browser-orchestrated catalogue batch processor.
 * Sequential requests keep serverless jobs bounded, status visible, and stop
 * behavior predictable. No hidden browser automation or credential capture.
 */
(() => {
 "use strict";
 const $ = id => document.getElementById(id);
 const start=$("batch-start");
 if(!start)return;
 const panel=$("batch-results"),feedback=$("batch-progress");
 const loaded=new Map();
 const files=[];
 let running=false,stopRequested=false,driveAvailable=false;
 const MAX=20;
 function status(text,style=""){
   feedback.textContent=text;
   feedback.className="notice "+style;
 }
 function normal(s){return String(s||"").toLowerCase().replace(/\s+/g," ").trim()}
 function clean(s){return String(s||"").replace(/\s+/g," ").trim()}
 function fileName(s){
   return clean(s).replace(/[^\w\- ]/g,"").slice(0,72)||"NUNES Catalogue";
 }
 function parseLines(text){
   const entries=[],seen=new Set();
   for(const input of String(text||"").split(/\r?\n/)){
     const line=input.trim();if(!line||line.startsWith("#"))continue;
     const parts=line.split("|");
     let name=clean(parts[0]),source=clean(parts[1]||"");
     if(name.startsWith("https://")){
       source=name;
       name=loaded.get(normal(source))?.product||"";
     }
     if(!name){throw Error("Give a product name before its URL, or import a matching Playwright JSON capture.")}
     if(name.length<4||name.length>170)throw Error("Invalid product name: "+name.slice(0,70));
     if(source){
       try{const url=new URL(source);if(url.protocol!=="https:"||
         !/(^|\.)indiamart\.com$/i.test(url.hostname)||
         !/\/(?:proddetail|product)\//i.test(url.pathname))throw Error();}
       catch(_){throw Error("Use a public IndiaMART product-detail HTTPS URL beside "+name);}
     }
     const key=normal(name);
     if(seen.has(key))continue;
     seen.add(key);
     entries.push({product:name,source_url:source});
     if(entries.length>MAX)throw Error("Use up to "+MAX+" products per run; split larger lists into batches.");
   }
   if(!entries.length)throw Error("Enter at least one product name.");
   return entries;
 }
 function resultRow(name){
   const row=document.createElement("div");
   row.className="batch-result-row";
   const head=document.createElement("strong");head.textContent=name;
   const state=document.createElement("span");state.className="batch-result-status";
   state.textContent="Waiting";
   const links=document.createElement("div");links.className="batch-result-links";
   row.append(head,state,links);panel.append(row);
   return {state,links};
 }
 function setRow(row,text,kind=""){
   row.state.textContent=text;row.state.className="batch-result-status "+kind;
 }
 function link(row,blob,name,caption){
   const url=URL.createObjectURL(blob);files.push(url);
   const a=document.createElement("a");a.href=url;a.download=name;
   a.textContent=caption;a.className="batch-pdf-link";row.links.append(a);
   return url;
 }
 function externalDriveLink(row,response,kind,wanted){
   const st=response.headers.get("X-Nunes-Drive-Status")||"";
   if(st==="saved"){
     const url=response.headers.get("X-Nunes-Drive-Link")||"";
     if(url.startsWith("https://drive.google.com/")){
       const a=document.createElement("a");a.target="_blank";
       a.rel="noopener noreferrer";a.href=url;
       a.textContent="Saved in Drive → "+(kind==="full"?"Catalogue":"Mini Catalogue");
       a.className="batch-drive-link";row.links.append(a);
     }
   }else if(wanted){
     const s=document.createElement("small");
     s.className="batch-drive-warning";
     s.textContent="Drive save not confirmed ("+(st||"not configured")+"). Local PDF is available.";
     row.links.append(s);
   }
   return st;
 }
 async function jsonFetch(url,body){
   const controller=new AbortController();
   const timer=setTimeout(()=>controller.abort(),90000);
   try{
     const response=await fetch(url,{
       method:"POST",cache:"no-store",
       headers:{"Content-Type":"application/json","X-Nunes-AI-Request":"1"},
       body:JSON.stringify(body),signal:controller.signal
     });
     const value=await response.json().catch(()=>({}));
     if(!response.ok)throw Error(value.error||"Source research failed (HTTP "+response.status+")");
     return value;
   }finally{clearTimeout(timer)}
 }
 async function pdfFetch(payload,owner,save){
   const headers={"Content-Type":"application/json"};
   if(save&&driveAvailable){
     headers["X-Nunes-Drive-Save"]="1";
     if(owner&&owner.length>=16)headers["X-Nunes-Drive-Token"]=owner;
   }
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),90000);
   try{
     const response=await fetch("/api/generate",{method:"POST",headers,
       body:JSON.stringify(payload),signal:controller.signal});
     if(!response.ok){
       const body=await response.json().catch(()=>({}));
       throw Error(body.error||"PDF rendering failed (HTTP "+response.status+")");
     }
     const blob=await response.blob();
     if(blob.size>5_500_000||blob.type&&!blob.type.includes("pdf"))
       throw Error("Unexpected PDF response");
     return {blob,response};
   }finally{clearTimeout(timer)}
 }
 function figureImported(entry){
   const direct=loaded.get(normal(entry.source_url));
   if(direct)return direct;
   return loaded.get(normal(entry.product))||null;
 }
 // Own-account CSV rows may include exact PUBLIC source evidence. Keep
 // this evidence only in this browser tab; never store session credentials.
 window.nunesBatchLoadSources=(rows)=>{
   loaded.clear();
   for(const row of Array.isArray(rows)?rows:[]){
     if(!row||!row.product||!row.source_url||!row.source_url.startsWith("https://"))continue;
     if(!row.description&&!row.specifications)continue;
     const capture={
       status:"captured",product:String(row.product),
       model:String(row.source_model||row.model||""),
       source_url:String(row.source_url),
       description:String(row.description||""),
       specifications:String(row.specifications||""),
       image_link:String(row.image_link||""),
       source:"owner_exported_product_details"
     };
     loaded.set(normal(capture.product),capture);
     loaded.set(normal(capture.source_url),capture);
   }
   $("batch-import-message").textContent=
     "Loaded owner-exported product details where exact public IndiaMART URLs are provided. "+
     "Original brand/model and supplied specification values remain subject to source review.";
 };
 const input=$("batch-playwright-json");
 input.onchange=async()=>{
   const file=input.files?.[0];if(!file)return;
   if(file.size>1_800_000){
     $("batch-import-message").textContent="Playwright JSON must be under 1.8 MB.";
     return;
   }
   try{
     const evidence=JSON.parse(await file.text());
     if(!Array.isArray(evidence.products))throw Error("Expected a 'products' array.");
     loaded.clear();
     const selections=[];
     for(const row of evidence.products.slice(0,100)){
       if(!row||row.status!=="captured"||!row.product||!row.source_url)continue;
       loaded.set(normal(row.product),row);
       loaded.set(normal(row.source_url),row);
       selections.push(row.product+" | "+row.source_url);
     }
     if(!selections.length)throw Error("No successfully captured public product records.");
     $("batch-products").value=selections.slice(0,MAX).join("\n");
     $("batch-import-message").textContent=
       "Imported "+selections.length+" captured product pages. First "+Math.min(MAX,selections.length)+
       " listed for this run. Source product descriptions and specifications still require review.";
   }catch(error){
     $("batch-import-message").textContent="Import failed: "+error.message;
   }
 };
 $("batch-use-selected").onclick=()=>{
   const found=[],known=new Set();
   const add=(name,url="")=>{
     name=clean(name);if(name.length<4||known.has(normal(name)))return;
     known.add(normal(name));
     found.push(name+(url?" | "+url:""));
   };
   if(typeof miniProducts!=="undefined"){
     try{miniProducts.filter(p=>p.selected).forEach(p=>add(p.product,p.source_url||""))}catch(_){}
   }
   if(!found.length){
     document.querySelectorAll("#source-links .nunes-gallery-card").forEach(card=>{
       const name=card.querySelector(".nunes-gallery-name")?.textContent;
       if(name)add(name);
     });
   }
   if(!found.length){
     const q=$("q")?.value.trim();if(q)add(q,$("indiamart-url")?.value.trim());
   }
   if(found.length){
     $("batch-products").value=found.slice(0,MAX).join("\n");
     status("Loaded "+Math.min(MAX,found.length)+" product name(s). Click Start Product List Automation.","success");
   }else status("Search products or enter names before importing selected products.","error");
 };
 $("batch-cancel").onclick=()=>{
   stopRequested=true;
   status("Stop requested. The current product will finish first.");
 };
 async function config(){
   try{
     const response=await fetch("/api/config",{cache:"no-store"});
     const result=await response.json();
     driveAvailable=Boolean(result.drive_save_available);
     const driveBox=$("batch-drive");
     driveBox.disabled=!driveAvailable;
     driveBox.checked=driveAvailable;
     const el=$("batch-drive-help");
     if(driveAvailable){
       el.textContent="Google Drive integration is configured. Enter your private owner/Drive code to save Full PDFs to Catalogue and Mini PDFs to Mini Catalogue.";
       el.className="batch-help success";
     }else{
       el.textContent="Google Drive not connected ("+(result.drive_save_issue||"configuration required")+
        "). PDFs can still be downloaded. To enable folder saving, configure the service account, parent folder and private save code in Vercel Production.";
       el.className="batch-help";
     }
   }catch(_){$("batch-drive-help").textContent="Unable to confirm Drive connection; local PDF downloads remain available.";}
 }
 config();
 start.onclick=async()=>{
   if(running)return;
   let entries;
   try{entries=parseLines($("batch-products").value)}
   catch(e){status(e.message,"error");return}
   const full=$("batch-full").checked,mini=$("batch-mini").checked;
   if(!full&&!mini){status("Choose Full PDFs, the combined Mini PDF, or both.","error");return}
   const owner=$("batch-owner-code").value.trim();
   const save=$("batch-drive").checked;
   if(save&&!driveAvailable){
     status("Drive save requested but Google Drive is not connected in Vercel. Uncheck Save to Drive to generate downloadable PDFs.","error");
     return;
   }
   running=true;stopRequested=false;
   start.disabled=true;$("batch-cancel").disabled=false;
   panel.replaceChildren();
   for(const url of files.splice(0))URL.revokeObjectURL(url);
   const results=[],rows=new Map();
   let completed=0,fullGenerated=0,failed=0,saved=0;
   const finished=[];
   try{
     for(let i=0;i<entries.length;i++){
       if(stopRequested)break;
       const entry=entries[i],row=resultRow(entry.product);
       rows.set(normal(entry.product),row);
       setRow(row,"Researching exact source…");
       status("Product "+(i+1)+"/"+entries.length+": "+entry.product);
       try{
         const draft=await jsonFetch("/api/catalogue/batch/prepare",{
           ...entry,batch_code:owner,scraped:figureImported(entry)
         });
         results.push(draft);completed++;
         const tag=draft.source_description_words+" scraped source words · "+
           draft.specification_count+" supported specs · "+
           (draft.image_link?"source photo":"no exact photo");
         setRow(row,"Prepared — "+tag);
         if(full){
           if(!draft.full_ready){
             const help=document.createElement("small");
             help.textContent="Full PDF held: "+(draft.specification_count?"matching photograph missing":
               "no explicit source-backed specification")+
               ". Mini PDF can still include this product by name.";
             help.className="batch-drive-warning";row.links.append(help);
           }else{
             setRow(row,"Rendering Full PDF…");
             const response=await pdfFetch({
               type:"full",product:draft.product,model:draft.source_model,
               specifications:draft.specifications,description:draft.description,
               features:draft.features.join("\n"),applications:"",
               image_link:draft.image_link,
               verification_acknowledged:"false"
             },owner,save);
             fullGenerated++;
             link(row,response.blob,fileName(draft.product)+"_Full.pdf","Download Full PDF");
             const savedStatus=externalDriveLink(row,response.response,"full",save);
             if(savedStatus==="saved")saved++;
             setRow(row,"Full PDF ready · "+tag,"success");
             finished.push(entry.product);
           }
         }
       }catch(e){
         failed++;
         setRow(row,"Needs review: "+e.message,"error");
       }
     }
     if(mini&&results.length&&!stopRequested){
       status("Creating one Mini PDF with "+results.length+" researched product name(s)…");
       const focus=results[0];
       const others=results.slice(1).map(p=>({
         product:p.product,model:p.source_model,image_link:p.image_link
       }));
       // A duplicate source item prevents a second discovery search if
       // the batch contains only one product.
       if(!others.length)others.push({product:focus.product,model:focus.source_model});
       const minis=await pdfFetch({
         type:"mini",product:focus.product,model:focus.source_model,
         image_link:focus.image_link,description:focus.description,
         features:focus.features.join("\n"),specifications:focus.specifications,
         related:others,keywords:results.map(p=>p.product).join(", ")
       },owner,save);
       const row=resultRow("Combined Mini Catalogue — "+results.length+" products");
       const blobUrl=link(row,minis.blob,
         fileName(focus.product)+"_"+results.length+"_Mini.pdf","Download Combined Mini PDF");
       const savedStatus=externalDriveLink(row,minis.response,"mini",save);
       if(savedStatus==="saved")saved++;
       setRow(row,"Mini PDF ready · "+results.length+" real product names","success");
       if(!full){
         for(const item of results)if(!finished.includes(item.product))finished.push(item.product);
       }
       // Show actual final PDF in existing preview panel for page review.
       if(typeof pdfUrl!=="undefined"){
         if(pdfUrl)URL.revokeObjectURL(pdfUrl);
         pdfUrl=URL.createObjectURL(minis.blob);
         pdfName=fileName(focus.product)+"_Mini.pdf";
         $("preview").replaceChildren();
         const frame=document.createElement("iframe");
         frame.src=pdfUrl+"#toolbar=1&view=FitH";
         frame.title="Generated combined Mini Catalogue PDF";
         $("preview").append(frame);
         $("previewtype").textContent="Combined Mini Catalogue PDF";
         $("download").disabled=false;$("zoomin").disabled=false;
         if(typeof window.nunesPdfPreviewUpdated==="function")
           window.nunesPdfPreviewUpdated(
             Number(minis.response.headers.get("X-Nunes-Page-Count")||0));
       }
     }
     status("Batch "+(stopRequested?"stopped":"finished")+": "+completed+
       " researched, "+fullGenerated+" Full PDF(s) created, "+
       (mini&&results.length&&!stopRequested?1:0)+" combined Mini PDF, "+
       failed+" item(s) requiring attention, "+saved+" saved to Drive."+
       (save&&!saved?" No Drive save was confirmed.":""),failed?"":"success");
     window.dispatchEvent(new CustomEvent("nunes:account-batch-finished",
       {detail:{completed:finished,failed,processed:completed}}));
   }catch(e){
     status("Batch interrupted: "+e.message+
       ". Created PDFs remain downloadable below.","error");
     window.dispatchEvent(new CustomEvent("nunes:account-batch-finished",
       {detail:{completed:finished,failed:failed+1,processed:completed}}));
   }
   finally{running=false;start.disabled=false;$("batch-cancel").disabled=true;}
 };
})();
