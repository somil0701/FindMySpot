<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h3 class="mb-0">My Reservations</h3>

      <div>
        <button class="btn btn-outline-secondary btn-sm me-2" :disabled="exporting" @click="exportClientSide">
          {{ exporting ? 'Exporting...' : 'Export CSV' }}
        </button>
        <a v-if="downloadUrl" :href="downloadUrl" class="btn btn-success btn-sm" target="_blank" rel="noopener">Download CSV</a>
      </div>
    </div>

    <div style="width: 250px; height: 250px; margin: auto;">
        <canvas id="chart"></canvas>
    </div>

    <div v-if="exportTaskId" class="mt-2">
      <small>Export task: {{ exportTaskId }} — status: <strong>{{ exportStatus }}</strong></small>
    </div>

    <ul class="list-group mt-4">
      <li v-for="r in reservations" :key="r.id" class="list-group-item">
        <div>
          <strong>Spot:</strong> {{ r.spot_id }}
          <br />
          <small>Start: {{ formatDate(r.start_time) }}</small>
          <br />
          <small>End: {{ r.end_time ? formatDate(r.end_time) : 'ACTIVE' }}</small>
          <br />
          <small>Duration: {{ computeDuration(r.start_time, r.end_time) }}</small>
          <br />
          <small>Cost: {{ displayCost(r) }}</small>

          <button
            v-if="!r.end_time"
            class="btn btn-warning btn-sm float-end"
            :disabled="releasing === r.id"
            @click="release(r.id)"
          >
            {{ releasing === r.id ? 'Releasing...' : 'Release' }}
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
export default {
  data() {
    return {
      reservations: [],
      chart: null,
      releasing: null,
      // export state
      exporting: false,
      exportTaskId: null,
      exportStatus: null,
      downloadUrl: null,
      exportPollInterval: null
    };
  },

  mounted() {
    this.load();
  },

  beforeUnmount(){
    if (this.chart) {
        try { this.chart.destroy(); } catch(e) {}
        this.chart = null;
    }
    if (this.exportPollInterval) {
      clearInterval(this.exportPollInterval);
      this.exportPollInterval = null;
    }
  },

  methods: {
    async load() {
      const user = JSON.parse(localStorage.getItem("user") || "null");
      if (!user) return;

      try {
        const r = await this.$axios.get(`/user/reservations/${user.id}`);
        this.reservations = r.data.reservations || [];
        this.drawChart();
      } catch (err) {
        console.error("Failed loading reservations:", err);
        this.reservations = [];
      }
    },

    async release(id) {
      try {
    // ask for optional release notes
    const extra = prompt("Add closing notes (optional):", "") || null;
    this.releasing = id;
    const r = await this.$axios.post("/user/release", { reservation_id: id, notes: extra });
    const cost = r?.data?.cost;
    alert("Released. Cost: " + (cost ?? "0"));
    this.load();
  } catch (err) {
    alert(err?.response?.data?.error || err?.message || "Failed to release.");
  } finally {
    this.releasing = null;
  }
    },

    // -------------------------
    // CSV export
    // -------------------------
    
    async exportClientSide() {
  try {
    // small guard
    const user = JSON.parse(localStorage.getItem("user") || "null");
    if (!user) { alert("Please log in to export data."); return; }

    this.exporting = true;

    // ensure we have all reservations for the user
    let data = this.reservations || [];
    try {
      const resp = await this.$axios.get(`/user/reservations/${user.id}`);
      data = resp?.data?.reservations || data;
    } catch (errFetch) {
      if (!data || data.length === 0) {
        throw new Error(errFetch?.response?.data?.error || "Failed to fetch reservations for export");
      } else {
        console.warn("Failed to fetch full reservations; exporting local copy", errFetch);
        alert("Could not fetch latest reservations; exporting data currently loaded in UI.");
      }
    }

    // Build CSV header and rows
    const headers = ["reservation_id","lot_id","lot_name","spot_id","spot_number","start_time","end_time","duration_seconds","cost","remarks"];
    const rows = [headers];

    const safe = (v) => {
      if (v === null || v === undefined) return "";
      if (typeof v === "object") return JSON.stringify(v);
      const s = String(v);
      if (s.indexOf('"') >= 0 || s.indexOf(',') >= 0 || s.indexOf('\n') >= 0) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    };

    for (const r of data) {
      // compute duration_seconds safely if not present
      let computedDuration = "";
      try {
        if (r.start_time && r.end_time) {
          const s = new Date(r.start_time);
          const e = new Date(r.end_time);
          if (!isNaN(s.getTime()) && !isNaN(e.getTime())) {
            computedDuration = Math.floor((e - s) / 1000);
          }
        }
      } catch (e) { /* ignore */ }

      const lotName = r.lot?.name ?? (r.lot_name ?? "");
      const lotId = r.lot?.id ?? (r.lot_id ?? "");
      const spotNumber = r.spot_number ?? r.spot_id ?? "";
      const cost = r.cost ?? "";
      // prefer duration from server if available, else computedDuration
      const durationFromServer = r.duration_seconds ?? r.duration_seconds_current ?? r.duaration_seconds ?? ""; // keep tolerant for older typos
      const durationFinal = durationFromServer !== "" ? durationFromServer : computedDuration;
      const remarks = r.remarks ?? r.notes ?? "";

      const line = [
        safe(r.id ?? r.reservation_id ?? ""),
        safe(lotId),
        safe(lotName),
        safe(r.spot_id ?? ""),
        safe(spotNumber),
        safe(r.start_time ?? ""),
        safe(r.end_time ?? ""),
        safe(durationFinal),
        safe(cost),
        safe(remarks)
      ];
      rows.push(line);
    }

    // Join rows into CSV string
    const csvContent = rows.map(r => r.join(",")).join("\r\n");

    // Add UTF-8 BOM so Excel opens UTF-8 CSV correctly
    const BOM = "\uFEFF";
    const blob = new Blob([BOM + csvContent], { type: "text/csv;charset=utf-8;" });

    // build filename
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `reservations_user_${user.id}_${ts}.csv`;

    // trigger download
    if (window.navigator && window.navigator.msSaveOrOpenBlob) {
      window.navigator.msSaveOrOpenBlob(blob, filename);
    } else {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.setAttribute("download", filename);
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }

    alert("CSV export started (saved to your Downloads).");
  } catch (err) {
    console.error("Export failed:", err);
    alert("Export failed: " + (err?.message || err));
  } finally {
    this.exporting = false;
  }
},


    startPollingExportStatus() {
      // clear any existing poller
      if (this.exportPollInterval) {
        clearInterval(this.exportPollInterval);
        this.exportPollInterval = null;
      }

      // poll every 2 seconds
      this.exportPollInterval = setInterval(async () => {
        if (!this.exportTaskId) return;
        try {
          const r = await this.$axios.get(`/export/status/${this.exportTaskId}`);
          this.exportStatus = r.data.state || r.data.status || "UNKNOWN";

          if (r.data.download_url) {
            this.downloadUrl = r.data.download_url;
          }

          if (this.exportStatus === "SUCCESS" || this.exportStatus === "FAILURE" || this.exportStatus === "REVOKED") {
            // stop polling
            clearInterval(this.exportPollInterval);
            this.exportPollInterval = null;
            this.exporting = false;

            if (this.exportStatus === "SUCCESS" && this.downloadUrl) {
              // optionally auto-open or notify
              // window.open(this.downloadUrl, "_blank");
            } else if (this.exportStatus !== "SUCCESS") {
              alert("Export failed. See server logs or retry.");
            }
          }
        } catch (err) {
          console.error("Export status poll error:", err);
          // keep polling a few times; but do not crash
        }
      }, 2000);
    },

    // small helpers reused from previous file
    drawChart() {
      const ctx = document.getElementById("chart");
      if (!ctx) return;

      if (this.chart){
        try { this.chart.destroy(); } catch(e) {}
        this.chart = null;
      }

      const ended = this.reservations.filter((r) => r.end_time).length;

      // create new chart instance
      this.chart = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: ["Completed", "Active"],
          datasets: [
            {
              data: [ended, this.reservations.length - ended],
            },
          ],
        },
      });
    },

    formatDate(iso) {
      if (!iso) return "";
      try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleString();
      } catch (e) {
        return iso;
      }
    },

    computeDuration(startIso, endIso) {
      if (!startIso) return "-";
      try {
        const start = new Date(startIso);
        const end = endIso ? new Date(endIso) : new Date();
        let seconds = Math.max(0, Math.floor((end - start) / 1000));
        const days = Math.floor(seconds / 86400);
        seconds -= days * 86400;
        const hours = Math.floor(seconds / 3600);
        seconds -= hours * 3600;
        const minutes = Math.floor(seconds / 60);
        if (days > 0) return `${days}d ${hours}h ${minutes}m`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
      } catch (e) {
        return "-";
      }
    },

    displayCost(resv) {
      if (!resv) return "-";
      const c = resv.cost ?? resv.amount_charged ?? resv.total;
      if (c !== undefined && c !== null) return c;
      return "-";
    }
  },
};
</script>
