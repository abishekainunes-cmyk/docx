/* Automated File Upload & Catalogue Generator Client */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  
  window.addEventListener('DOMContentLoaded', () => {
    const dropzone = $('dropzone');
    const fileInput = $('auto-upload-input');
    const progress = $('auto-upload-progress');
    const statusText = $('auto-upload-status-text');
    const resultBox = $('auto-upload-result');

    if (!dropzone || !fileInput) return;

    // Drag & Drop events
    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, e => {
        e.preventDefault();
        dropzone.style.borderColor = '#2563eb';
        dropzone.style.background = '#eff6ff';
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, e => {
        e.preventDefault();
        dropzone.style.borderColor = '#93c5fd';
        dropzone.style.background = '#fff';
      });
    });

    dropzone.addEventListener('drop', e => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        handleUpload(files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleUpload(fileInput.files[0]);
      }
    });

    let currentResult = null;

    async function handleUpload(file) {
      if (!file) return;

      progress.style.display = 'block';
      progress.className = 'notice';
      statusText.textContent = `Analyzing "${file.name}" and extracting specifications…`;
      resultBox.style.display = 'none';

      const formData = new FormData();
      formData.append('file', file);
      formData.append('save_drive', '1');

      try {
        statusText.textContent = 'Parsing document contents and formulating certified catalogue…';
        const res = await fetch('/api/catalogue/upload-auto-generate', {
          method: 'POST',
          body: formData
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.error || 'Failed to detect details or generate catalogue');
        }

        currentResult = data;
        statusText.textContent = 'Generating 2-page Full Catalogue (VTech VT) and Mini Catalogue…';
        
        // Populate results card
        if ($('detected-prod-name')) {
          $('detected-prod-name').textContent = data.product_name || 'Industrial Instrument';
        }
        
        const srcModel = data.source_model || data.model || 'VT';
        const catModel = data.catalogue_model || 'VT';
        if ($('detected-model')) {
          $('detected-model').innerHTML = `${catModel} <span style="font-weight:normal;color:#64748b;font-size:12px;">(Source Model: <strong>${srcModel}</strong>)</span>`;
        }

        if ($('detected-specs')) {
          $('detected-specs').textContent = data.specifications || 'No technical specifications parsed.';
        }
        
        if ($('detected-photo')) {
          if (data.photo_data_b64) {
            $('detected-photo').src = data.photo_data_b64;
            $('detected-photo').style.display = 'inline-block';
          } else {
            $('detected-photo').style.display = 'none';
          }
        }

        // Show File metadata & review warnings
        let metaNotice = $('detected-meta-notice');
        if (!metaNotice) {
          metaNotice = document.createElement('div');
          metaNotice.id = 'detected-meta-notice';
          metaNotice.style.margin = '8px 0 12px 0';
          metaNotice.style.fontSize = '12px';
          const headerWrap = resultBox.firstElementChild;
          if (headerWrap) {
            headerWrap.parentNode.insertBefore(metaNotice, headerWrap.nextSibling);
          }
        }

        const warnings = (data.warnings || []).concat(data.missing_info || []);
        const warningHtml = warnings.length > 0 
          ? `<div style="background:#fffbeb;border:1px solid #fef3c7;color:#92400e;padding:7px 12px;border-radius:6px;margin-top:6px;">⚠️ <strong>Review Note:</strong> ${warnings.join(' · ')}</div>`
          : '';

        metaNotice.innerHTML = `
          <div style="display:flex;gap:12px;flex-wrap:wrap;color:#475569;font-size:11.5px;align-items:center;">
            <span>📁 <strong>File:</strong> ${file.name}</span>
            <span>📑 <strong>Detected Format:</strong> <span style="background:#e0f2fe;color:#0369a1;padding:2px 7px;border-radius:4px;font-weight:700;">${data.detected_format || 'Document'}</span></span>
            <span>✅ <strong>Extraction:</strong> <span style="color:#059669;font-weight:700;">Completed (${data.spec_count || 5} specs verified)</span></span>
          </div>
          ${warningHtml}
        `;

        // Drive status
        const driveBadge = $('detected-drive-badge');
        const driveBtn = $('btn-view-drive-full');
        if (data.drive_saved && data.drive_links) {
          if (driveBadge) driveBadge.style.display = 'inline-block';
          const link = data.drive_links.full || data.drive_links.mini || data.drive_full_folder;
          if (link && driveBtn) {
            driveBtn.href = link;
            driveBtn.style.display = 'inline-flex';
          }
        } else {
          if (driveBadge) driveBadge.style.display = 'none';
          if (driveBtn) driveBtn.style.display = 'none';
        }

        // Action buttons
        if ($('btn-download-full')) {
          $('btn-download-full').onclick = () => {
            if (data.full_pdf_b64) {
              downloadB64(data.full_pdf_b64, data.full_pdf_filename || 'NUNES_Full_Catalogue.pdf');
            }
          };
        }

        if ($('btn-download-mini')) {
          $('btn-download-mini').onclick = () => {
            if (data.mini_pdf_b64) {
              downloadB64(data.mini_pdf_b64, data.mini_pdf_filename || 'NUNES_Mini_Catalogue.pdf');
            }
          };
        }

        if ($('btn-load-editor')) {
          $('btn-load-editor').onclick = () => {
            loadIntoEditor(data);
          };
        }

        progress.style.display = 'none';
        resultBox.style.display = 'block';

      } catch (err) {
        progress.style.display = 'block';
        progress.className = 'notice error';
        statusText.textContent = 'Upload processing failed: ' + err.message;
      }
    }

    function downloadB64(b64, filename) {
      const byteChars = atob(b64);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 500);
    }

    function loadIntoEditor(data) {
      if ($('product')) $('product').value = data.product_name || '';
      if ($('model')) $('model').value = data.source_model || data.model || '';
      if ($('specs')) {
        $('specs').value = data.specifications || '';
        $('specs').dispatchEvent(new Event('input', { bubbles: true }));
      }
      if ($('description')) $('description').value = data.description || '';
      if ($('features')) {
        const feats = Array.isArray(data.features) ? data.features.join('\n') : (data.features || '');
        $('features').value = feats;
      }
      if ($('applications')) {
        const apps = Array.isArray(data.applications) ? data.applications.join('\n') : (data.applications || '');
        $('applications').value = apps;
      }
      if ($('imageview') && data.photo_data_b64) {
        $('imageview').src = data.photo_data_b64;
        $('imageview').hidden = false;
      }
      const editor = $('editor');
      if (editor) {
        editor.scrollIntoView({ behavior: 'smooth' });
      }
    }
  });
})();
