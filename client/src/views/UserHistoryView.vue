<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h3 class="mb-0">My Parking History</h3>
      <div>
        <button class="btn btn-outline-secondary btn-sm" @click="$root.view = 'UserDash'">Back to My Parking</button>
        <button class="btn btn-outline-primary btn-sm" @click="load">Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="text-center my-3">Loading history...</div>
    <div v-if="!loading && reservations.length === 0" class="alert alert-info">No reservations found.</div>

    <div v-if="!loading && reservations.length">
      <table class="table table-sm">
        <thead>
          <tr>
            <th>ID</th>
            <th>Lot</th>
            <th>Spot</th>
            <th>Start</th>
            <th>End</th>
            <th>Duration</th>
            <th>Cost</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in reservations" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.lot?.name || '-' }}</td>
            <td>{{ r.spot_number || '-' }}</td>
            <td>{{ formatDate(r.start_time) }}</td>
            <td>{{ formatDate(r.end_time) }}</td>
            <td>{{ computeDuration(r.start_time, r.end_time, r.duration_seconds) }}</td>
            <td>{{ displayCost(r.cost) }}</td>
            <td>{{ r.notes || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      reservations: [],
      loading: false
    };
  },

  mounted() {
    this.load();
  },

  methods: {
    async load() {
      this.loading = true;
      try {
        const r = await this.$axios.get('/user/history');
        this.reservations = r.data.reservations || [];
      } catch (err) {
        console.error('Failed to load history', err);
        alert('Failed to load history. Make sure you are logged in.');
        this.reservations = [];
      } finally {
        this.loading = false;
      }
    },

    formatDate(iso) {
      if (!iso) return '-';
      try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleString();
      } catch (e) {
        return iso;
      }
    },

    computeDuration(startIso, endIso, knownDurationSeconds) {
      try {
        let seconds = null;
        if (typeof knownDurationSeconds === 'number' && !Number.isNaN(knownDurationSeconds)) {
          seconds = knownDurationSeconds;
        } else if (startIso) {
          const start = new Date(startIso);
          const end = endIso ? new Date(endIso) : new Date();
          if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())) {
            seconds = Math.max(0, Math.floor((end - start) / 1000));
          }
        }
        if (seconds === null) return '-';
        const days = Math.floor(seconds / 86400);
        seconds -= days * 86400;
        const hours = Math.floor(seconds / 3600);
        seconds -= hours * 3600;
        const minutes = Math.floor(seconds / 60);
        if (days > 0) return `${days}d ${hours}h ${minutes}m`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
      } catch (e) {
        return '-';
      }
    },

    displayCost(c) {
      if (c === null || c === undefined) return '-';
      try { return Number(c).toFixed(2); } catch { return String(c); }
    }
  }
};
</script>

<style scoped>
.table { font-size: 0.95rem; }
</style>
