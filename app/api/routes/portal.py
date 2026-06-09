from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.tenant_service import TenantService

router = APIRouter()
tenant_service = TenantService()


@router.get("/portal/{tenant_id}", response_class=HTMLResponse)
async def admin_portal(tenant_id: str):
    """
    Simple admin portal for a business owner.
    No login required for Week 3 — Week 4 adds auth.
    """
    tenant = tenant_service.get_tenant(tenant_id)

    if not tenant:
        return HTMLResponse(
            content="<h2>Tenant not found. Check your tenant ID.</h2>",
            status_code=404
        )

    name = tenant["name"]
    collection = tenant["collection_name"]
    phones = ", ".join(tenant["whatsapp_numbers"]) or "None registered yet"

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{name} — Admin Portal</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0f2f5;
      color: #1a1a1a;
      min-height: 100vh;
      padding: 40px 20px;
    }}

    .container {{
      max-width: 640px;
      margin: 0 auto;
    }}

    .header {{
      background: #25d366;
      color: white;
      border-radius: 12px;
      padding: 28px 32px;
      margin-bottom: 24px;
    }}

    .header h1 {{
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 4px;
    }}

    .header p {{
      opacity: 0.85;
      font-size: 14px;
    }}

    .card {{
      background: white;
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}

    .card h2 {{
      font-size: 15px;
      font-weight: 600;
      color: #555;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 16px;
    }}

    .stat-row {{
      display: flex;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid #f0f0f0;
      font-size: 14px;
    }}

    .stat-row:last-child {{ border-bottom: none; }}
    .stat-label {{ color: #888; }}
    .stat-value {{ font-weight: 500; }}

    .stat-number {{
      font-size: 36px;
      font-weight: 700;
      color: #25d366;
    }}

    .upload-area {{
      border: 2px dashed #d0d0d0;
      border-radius: 10px;
      padding: 32px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
      margin-bottom: 16px;
    }}

    .upload-area:hover,
    .upload-area.drag-over {{
      border-color: #25d366;
      background: #f0fff4;
    }}

    .upload-area .icon {{ font-size: 36px; margin-bottom: 8px; }}
    .upload-area p {{ color: #888; font-size: 14px; }}
    .upload-area strong {{ color: #1a1a1a; }}

    #fileInput {{ display: none; }}

    .btn {{
      background: #25d366;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 12px 28px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      width: 100%;
      transition: background 0.2s;
    }}

    .btn:hover {{ background: #1ebe5d; }}
    .btn:disabled {{ background: #ccc; cursor: not-allowed; }}

    .progress {{
      display: none;
      margin-top: 16px;
    }}

    .progress-bar {{
      height: 6px;
      background: #e0e0e0;
      border-radius: 4px;
      overflow: hidden;
    }}

    .progress-fill {{
      height: 100%;
      background: #25d366;
      width: 0%;
      transition: width 0.3s;
      animation: indeterminate 1.5s infinite;
    }}

    @keyframes indeterminate {{
      0% {{ width: 0%; margin-left: 0%; }}
      50% {{ width: 60%; margin-left: 20%; }}
      100% {{ width: 0%; margin-left: 100%; }}
    }}

    .result {{
      display: none;
      margin-top: 16px;
      padding: 14px;
      border-radius: 8px;
      font-size: 14px;
    }}

    .result.success {{
      background: #f0fff4;
      border: 1px solid #25d366;
      color: #1a7a40;
    }}

    .result.error {{
      background: #fff0f0;
      border: 1px solid #ff4d4f;
      color: #a00;
    }}

    .history-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid #f0f0f0;
      font-size: 14px;
    }}

    .history-item:last-child {{ border-bottom: none; }}
    .history-icon {{ font-size: 20px; }}
    .history-meta {{ color: #888; font-size: 12px; }}
  </style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>📋 {name}</h1>
    <p>WhatsApp AI Agent — Admin Portal</p>
  </div>

  <!-- Stats -->
  <div class="card">
    <h2>Bot Status</h2>
    <div class="stat-row">
      <span class="stat-label">Tenant ID</span>
      <span class="stat-value">{tenant_id}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">WhatsApp Numbers</span>
      <span class="stat-value">{phones}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Knowledge Base</span>
      <span class="stat-value">{collection}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Chunks Stored</span>
      <span class="stat-value" id="chunkCount">Loading...</span>
    </div>
  </div>

  <!-- Upload -->
  <div class="card">
    <h2>Upload Documents</h2>

    <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
      <div class="icon">📄</div>
      <strong id="fileName">Click to select a PDF</strong>
      <p>or drag and drop here</p>
    </div>

    <input type="file" id="fileInput" accept=".pdf"/>

    <button class="btn" id="uploadBtn" onclick="uploadFile()" disabled>
      Upload & Train Bot
    </button>

    <div class="progress" id="progress">
      <div class="progress-bar"><div class="progress-fill"></div></div>
      <p style="text-align:center; margin-top:8px; font-size:13px; color:#888">
        Processing PDF — this may take 30–60 seconds...
      </p>
    </div>

    <div class="result" id="result"></div>
  </div>

  <!-- Upload history placeholder -->
  <div class="card">
    <h2>Recent Uploads</h2>
    <div id="uploadHistory">
      <p style="color:#aaa; font-size:14px; text-align:center; padding:16px 0">
        No uploads yet. Upload a PDF above to get started.
      </p>
    </div>
  </div>

</div>

<script>
  const tenantId = "{tenant_id}";
  let selectedFile = null;
  let uploadHistory = JSON.parse(localStorage.getItem('uploads_' + tenantId) || '[]');

  // Load chunk count
  async function loadStats() {{
    try {{
      const res = await fetch(`/api/v1/tenants/${{tenantId}}/stats`);
      const data = await res.json();
      document.getElementById('chunkCount').textContent = data.total_chunks + ' chunks';
    }} catch(e) {{
      document.getElementById('chunkCount').textContent = 'Error loading';
    }}
  }}

  // Render upload history
  function renderHistory() {{
    const el = document.getElementById('uploadHistory');
    if (uploadHistory.length === 0) {{
      el.innerHTML = '<p style="color:#aaa; font-size:14px; text-align:center; padding:16px 0">No uploads yet.</p>';
      return;
    }}
    el.innerHTML = uploadHistory.slice().reverse().map(u => `
      <div class="history-item">
        <span class="history-icon">✅</span>
        <div>
          <div style="font-weight:500">${{u.filename}}</div>
          <div class="history-meta">${{u.pages}} pages · ${{u.chunks}} chunks · ${{u.time}}</div>
        </div>
      </div>
    `).join('');
  }}
  

  // File selection
  document.getElementById('fileInput').addEventListener('change', function() {{
    selectedFile = this.files[0];
    if (selectedFile) {{
      document.getElementById('fileName').textContent = selectedFile.name;
      document.getElementById('uploadBtn').disabled = false;
    }}
  }});

  // Drag and drop
  const area = document.getElementById('uploadArea');
  area.addEventListener('dragover', e => {{ e.preventDefault(); area.classList.add('drag-over'); }});
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', e => {{
    e.preventDefault();
    area.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.pdf')) {{
      selectedFile = file;
      document.getElementById('fileName').textContent = file.name;
      document.getElementById('uploadBtn').disabled = false;
    }}
  }});

  // Upload
  async function uploadFile() {{
    if (!selectedFile) return;

    document.getElementById('uploadBtn').disabled = true;
    document.getElementById('progress').style.display = 'block';
    document.getElementById('result').style.display = 'none';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {{
      const res = await fetch(`/api/v1/tenants/${{tenantId}}/ingest`, {{
        method: 'POST',
        body: formData,
      }});

      const data = await res.json();
      document.getElementById('progress').style.display = 'none';

      if (res.ok) {{
        const result = document.getElementById('result');
        result.className = 'result success';

        // Handle both sync and async (background job) responses
        const filename = data.filename || selectedFile.name;
        const pages = data.pages_processed ?? '(processing...)';
        const chunks = data.chunks_created ?? '(processing...)';
        const jobId = data.job_id;

        result.innerHTML = `
          ✅ <strong>${{filename}}</strong> uploaded successfully!<br>
          ${{pages}} pages · ${{chunks}} chunks stored
          ${{jobId ? `<br><small>Job ID: ${{jobId}} — chunks will appear shortly</small>` : ''}}
        `;
        result.style.display = 'block';

        uploadHistory.push({{
          filename: filename,
          pages: pages,
          chunks: chunks,
          time: new Date().toLocaleString(),
        }});
        localStorage.setItem('uploads_' + tenantId, JSON.stringify(uploadHistory));
        renderHistory();
        
        // Poll for job completion if background processing
        if (jobId) {{
          pollJobStatus(jobId);
        }} else {{
          loadStats();
        }}
      }} else {{
        showError(data.detail || 'Upload failed');
      }}
    }} catch(e) {{
      document.getElementById('progress').style.display = 'none';
      showError('Network error — is the server running?');
    }}

    document.getElementById('uploadBtn').disabled = false;
    selectedFile = null;
    document.getElementById('fileName').textContent = 'Click to select a PDF';
    document.getElementById('fileInput').value = '';
  }}

  function showError(msg) {{
    const result = document.getElementById('result');
    result.className = 'result error';
    result.innerHTML = '❌ ' + msg;
    result.style.display = 'block';
  }}
    // Poll background job status
  async function pollJobStatus(jobId) {{
    const maxAttempts = 20;
    let attempts = 0;

    const interval = setInterval(async () => {{
      attempts++;

      try {{
        const res = await fetch(`/api/v1/jobs/${{jobId}}`);
        const job = await res.json();

        if (job.status === 'completed') {{
          clearInterval(interval);

          loadStats();

          document.getElementById('result').innerHTML +=
            `<br>✅ Processing complete: ${{job.result.pages_processed}} pages · ${{job.result.chunks_created}} chunks`;
        }}
        else if (job.status === 'failed') {{
          clearInterval(interval);
          showError('Processing failed: ' + job.error);
        }}
      }}
      catch (e) {{
        clearInterval(interval);
        console.error(e);
      }}

      if (attempts >= maxAttempts) {{
        clearInterval(interval);
      }}
    }}, 3000); // check every 3 seconds
  }}

  // Init
  loadStats();
  renderHistory();
</script>
</body>
</html>
"""
    return HTMLResponse(content=html)