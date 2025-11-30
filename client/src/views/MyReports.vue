<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h3 class="mb-0">My Reports</h3>
      <div>
        <button class="btn btn-outline-secondary btn-sm me-2" @click="$root.view = 'UserDash'">Back</button>
        <button class="btn btn-primary btn-sm" :disabled="starting" @click="startExport">
          {{ starting ? 'Starting...' : 'Generate Report (CSV)' }}
        </button>
      </div>
    </div>

    <div v-if="taskId" class="mb-3">
      <small>Export task: <strong>{{ taskId }}</strong> — status: <strong>{{ taskStatus }}</strong></small>
    </div>

    <div class="mb-3">
      <button class="btn btn-sm btn-outline-info me-2" @click="refreshList">Refresh list</button>
      <small class="text-muted">Exports are generated server-side and stored for download.</small>
    </div>

    <div v-if="loading" class="text-center py-2">Loading...</div>

    <div v-if="!loading && files.length === 0" class="alert alert-info">You have no exported reports yet.</div>

    <table v-if="files.length" class="table table-sm">
      <thead>
        <tr>
          <th>Created</th>
          <th>Filename</th>
          <th>Size</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in files" :key="f.filename">
          <td>{{ formatDate(f.created_at) }}</td>
          <td>{{ f.filename }}</td>
          <td>{{ humanSize(f.size_bytes) }}</td>
          <td>
            <button class="btn btn-sm btn-success" @click="downloadFile(f)" :disabled="downloading === f.filename">
              {{ downloading === f.filename ? 'Downloading...' : 'Download' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="error" class="alert alert-danger mt-3">{{ error }}</div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      files: [],
      loading: false,
      error: null,
      starting: false,
      taskId: null,
      taskStatus: null,
      pollInterval: null,
      downloading: null
    };
  },

  mounted() {
    this.refreshList();
  },

  beforeUnmount() {
    if (this.pollInterval) clearInterval(this.pollInterval);
  },

  methods: {
    formatDate(iso) {
      if (!iso) return '';
      try {
        const d = new Date(iso);
        return d.toLocaleString();
      } catch (e) { return iso; }
    },

    humanSize(bytes) {
      if (!bytes && bytes !== 0) return '-';
      const units = ['B','KB','MB','GB'];
      let i = 0;
      let v = Number(bytes);
      while (v >= 1024 && i < units.length - 1) {
        v /= 1024; i++;
      }
      return `${v.toFixed(1)} ${units[i]}`;
    },

    async refreshList() {
      this.loading = true;
      this.error = null;
      try {
        const resp = await this.$axios.get('/export/list');
        this.files = resp.data.files || [];
      } catch (err) {
        console.error('Failed to list exports', err);
        this.error = err?.response?.data?.error || err?.message || 'Failed to list exports';
      } finally {
        this.loading = false;
      }
    },

    async startExport() {
      const user = JSON.parse(localStorage.getItem('user') || 'null');
      if (!user) { alert('Please log in to generate reports.'); return; }

      this.starting = true;
      this.error = null;
      try {
        const r = await this.$axios.post(`/export/${user.id}`);
        const taskId = r.data.task_id;
        if (taskId) {
          this.taskId = taskId;
          this.taskStatus = 'PENDING';
          this.startPolling();
        } else {
          alert('Export started but no task id returned.');
        }
      } catch (err) {
        console.error('Failed to start export', err);
        this.error = err?.response?.data?.error || err?.message || 'Failed to start export';
      } finally {
        this.starting = false;
      }
    },

    startPolling() {
      if (this.pollInterval) clearInterval(this.pollInterval);
      this.pollInterval = setInterval(this.pollStatus, 2000);
      this.pollStatus();
    },

    async pollStatus() {
      if (!this.taskId) return;
      try {
        const r = await this.$axios.get(`/export/status/${this.taskId}`);
        this.taskStatus = r.data.state || r.data.status || 'UNKNOWN';
        if (r.data.download_url) {
          await this.refreshList();
          clearInterval(this.pollInterval);
          this.pollInterval = null;
        }
        if (['SUCCESS','FAILURE','REVOKED'].includes(this.taskStatus)) {
          if (this.pollInterval) { clearInterval(this.pollInterval); this.pollInterval = null; }
        }
      } catch (err) {
        console.error('Export status poll error', err);
      }
    },

    // Secure authenticated download using axios + blob
    async downloadFile(fileMeta) {
      if (!fileMeta || !fileMeta.filename || !fileMeta.download_url) {
        alert('Invalid file metadata');
        return;
      }

      // require token
      const token = localStorage.getItem('token');
      if (!token) {
        alert('Please login to download files.');
        return;
      }

      const url = fileMeta.download_url;
      this.downloading = fileMeta.filename;
      this.error = null;

      try {
        const resp = await this.$axios.get(url, {
          responseType: 'blob',
          // axios will already include Authorization header if defaults set (login sets it),
          // but set it explicitly to be safe
          headers: {
            Authorization: 'Bearer ' + token
          }
        });

        // derive filename from response headers if present, else fallback to fileMeta.filename
        let suggestedName = fileMeta.filename || 'report';
        try {
          const cd = resp.headers && resp.headers['content-disposition'];
          if (cd) {
            const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/.exec(cd);
            if (m) suggestedName = decodeURIComponent(m[1] || m[2]);
          }
        } catch (e) { /* ignore */ }

        const blob = new Blob([resp.data], { type: resp.data.type || 'application/octet-stream' });
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = suggestedName;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(blobUrl);
      } catch (err) {
        console.error('Download failed', err);
        // server may return JSON error (not blob) — try to extract message
        let msg = err?.message || 'Download failed';
        if (err?.response && err.response.data) {
          try {
            // if server returned JSON error body, try to read it
            const reader = new FileReader();
            const data = err.response.data;
            if (data instanceof Blob) {
              // attempt to parse JSON error from blob
              const text = await data.text();
              try { msg = JSON.parse(text).error || JSON.parse(text).message || text; } catch(e){ msg = text; }
            } else if (typeof data === 'string') {
              msg = data;
            }
          } catch (e) {}
        }
        this.error = String(msg);
        alert('Download failed: ' + this.error);
      } finally {
        this.downloading = null;
      }
    }
  }
};
</script>

<style scoped>
.table { font-size: 0.95rem; }
</style>
