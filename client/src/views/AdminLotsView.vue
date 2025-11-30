<template>
  <div>
    <div class="d-flex justify-content-between align-items-start mb-3">
      <h3 class="mb-0">Admin — Manage Parking Lots</h3>

      <!-- NEW: Generate monthly reports button -->
      <div class="ms-auto d-flex gap-2 align-items-center">
        <button class="btn btn-sm btn-outline-primary" :disabled="generating" @click="generateMonthlyReports">
          {{ generating ? 'Generating...' : 'Generate Monthly Reports Now' }}
        </button>
      </div>
    </div>

    <div v-if="genTaskId" class="mb-2">
      <small>Report Task: <strong>{{ genTaskId }}</strong> — status: <strong>{{ genStatus }}</strong></small>
      <button v-if="genStatus !== 'SUCCESS' && genStatus !== 'FAILURE'" class="btn btn-sm btn-link" @click="stopGenPoll">Stop Poll</button>
    </div>

    <form class="row g-2 mb-4" @submit.prevent="createLot">
      <div class="col-auto">
        <input class="form-control" v-model="name" placeholder="Lot name" required />
      </div>

      <div class="col-auto">
        <input class="form-control" v-model="address" placeholder="Address" />
      </div>

      <div class="col-auto">
        <input type="number" class="form-control" v-model.number="capacity" min="1" placeholder="Capacity" required />
      </div>

      <div class="col-auto">
        <input type="number" class="form-control" v-model.number="price" placeholder="Price/hr" step="0.5" required />
      </div>

      <div class="col-auto">
        <button class="btn btn-primary">Create</button>
      </div>
    </form>

    <!-- inside Admin page where appropriate -->
    <button class="btn btn-link" @click="loadUsers">Manage Users</button>
    <div v-if="users.length">
      <div v-for="u in users" :key="u.id" class="card p-2 mb-1">
        <div>{{ u.username }} ({{ u.email }})</div>
        <button class="btn btn-sm btn-outline-primary" @click="loadUserReservations(u.id)">View Reservations</button>
      </div>
    </div>

    <div v-if="userReservations.length">
      <h6>User Reservations</h6>
      <div v-for="r in userReservations" :key="r.id">
        <small>Lot: {{ r.lot?.name }} • Spot: {{ r.spot_number }}</small>
        <div>Start: {{ r.start_time }}, End: {{ r.end_time }}, Cost: {{ r.cost }}</div>
      </div>
    </div>


    <div class="mt-3">
      <h5>Lots</h5>
      <div v-for="lot in lots" :key="lot.id" class="card mb-2 p-2">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <strong>{{ lot.name }}</strong><br/>
            <small class="text-muted">{{ lot.address }}</small><br/>
            <small>Price/hr: {{ lot.price_per_hour }} • Capacity: {{ lot.capacity }}</small>
          </div>
          <div>
            <button class="btn btn-sm btn-info me-1" @click="viewSpots(lot.id)">View Spots</button>
            <button class="btn btn-sm btn-danger" @click="remove(lot.id)">Delete</button>
          </div>
        </div>

        <div v-if="selectedLot && selectedLot.id === lot.id" class="mt-2">
          <h6>Spots</h6>
          <div v-if="spotsLoading">Loading spots...</div>
          <div v-else>
            <div v-for="(s, idx) in spots" :key="s.id" class="border rounded p-2 mb-1 d-flex justify-content-between align-items-center">
              <div>
                <strong>#{{ s.number }}</strong>
                <span class="ms-2 badge" :class="s.status === 'O' ? 'bg-danger' : 'bg-success'">
                  {{ s.status === 'O' ? 'Occupied' : 'Available' }}
                </span>

                <div v-if="s.current_reservation" class="mt-1">
                  <small class="d-block">User: {{ s.current_reservation.user.username }} ({{ s.current_reservation.user.email }})</small>
                  <small>Start: {{ s.current_reservation.start_time }}</small>
                  <small>Notes: {{ s.current_reservation.notes }}</small>
                  <!-- NEW: extra metadata show duration/cost if ended -->
                  <div v-if="s.current_reservation.end_time">
                    <small>End: {{ s.current_reservation.end_time }}</small>
                    <small>Duration: {{ computeDuration(s.current_reservation.start_time, s.current_reservation.end_time) }}</small>
                    <small>Cost: {{ s.current_reservation.cost }}</small>
                  </div>
                </div>
              </div>

              <div class="d-flex gap-2 align-items-center">
                <!-- Edit button toggles inline editor -->
                <button class="btn btn-sm btn-outline-secondary" @click="toggleEditSpot(s, idx)">
                  {{ editingSpotId === s.id ? 'Cancel' : 'Edit' }}
                </button>

                <button v-if="editingSpotId === s.id" class="btn btn-sm btn-primary" @click="saveEdit(s, idx)">Save</button>
              </div>
            </div>

            <!-- Inline editor row placed below the list when editing -->
            <div v-if="editingSpotId && editingIndex !== null" class="card p-2 mb-2">
              <div class="row g-2 align-items-center">
                <div class="col-auto">
                  <label class="form-label mb-0">Number</label>
                  <input class="form-control" v-model="editForm.number" />
                </div>
                <div class="col-auto">
                  <label class="form-label mb-0">Status</label>
                  <select class="form-select" v-model="editForm.status">
                    <option value="A">Available</option>
                    <option value="O">Occupied</option>
                  </select>
                </div>
                <div class="col-auto">
                  <label class="form-label mb-0">Notes (optional)</label>
                  <input class="form-control" v-model="editForm.notes" placeholder="Admin note" />
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
export default {
  data() {
    return {
      name: "",
      address: "",
      capacity: 5,
      price: 10,
      lots: [],
      users: [],
      userReservations: [],
      selectedLot: null,
      spots: [],
      spotsLoading: false,
      // editing state
      editingSpotId: null,
      editingIndex: null,
      editForm: { number: '', status: 'A', notes: '' },

      // NEW: generate reports state
      generating: false,
      genTaskId: null,
      genStatus: null,
      genPollInterval: null
    };
  },

  mounted() {
    this.load();
  },

  beforeUnmount() {
    if (this.genPollInterval) {
      clearInterval(this.genPollInterval);
      this.genPollInterval = null;
    }
  },

  methods: {
    async load() {
      try {
        const r = await this.$axios.get("/api/lots/summary");
        this.lots = r.data.summary.map((s) => s.lot);
      } catch (e) {
        console.error(e);
      }
    },

    async createLot() {
      try {
        await this.$axios.post("/admin/lots", {
          name: this.name,
          address: this.address,
          capacity: this.capacity,
          price_per_hour: this.price,
        });
        alert("Lot created.");
        this.name = "";
        this.load();
      } catch (e) {
        alert("Error creating lot: " + (e?.response?.data?.error || e.message));
      }
    },

    async remove(id) {
      if (!confirm("Delete this lot?")) return;
      try {
        await this.$axios.delete(`/admin/lots/${id}`);
        this.load();
      } catch (e) {
        alert("Cannot delete (maybe spot occupied). " + (e?.response?.data?.error || ""));
      }
    },

    async viewSpots(lotId) {
      try {
        this.selectedLot = { id: lotId };
        this.spotsLoading = true;
        const r = await this.$axios.get(`/admin/lots/${lotId}/spots`);
        this.spots = r.data.spots || [];
        // reset editor state
        this.editingSpotId = null;
        this.editingIndex = null;
        this.editForm = { number: '', status: 'A', notes: '' };
      } catch (err) {
        console.error(err);
        alert("Failed to load spots. Are you logged in as admin?");
      } finally {
        this.spotsLoading = false;
      }
    },

    async loadUsers() {
      try {
        const r = await this.$axios.get("/admin/users");
        this.users = r.data.users || [];
      } catch (err) {
        alert("Failed to load users (need admin token).");
      }
    },

    async loadUserReservations(userId) {
      try {
        const r = await this.$axios.get(`/admin/users/${userId}/reservations`);
        this.userReservations = r.data.reservations || [];
      } catch (err) {
        alert("Failed to load user reservations.");
      }
    },

    toggleEditSpot(spot, idx) {
      if (this.editingSpotId === spot.id) {
        // cancel
        this.editingSpotId = null;
        this.editingIndex = null;
        this.editForm = { number: '', status: 'A', notes: '' };
      } else {
        // start editing
        this.editingSpotId = spot.id;
        this.editingIndex = idx;
        this.editForm = { number: spot.number, status: spot.status || 'A', notes: spot.current_reservation?.notes || '' };
        // scroll into view slightly
        this.$nextTick(() => {
          try { window.scrollTo({ top: document.body.scrollHeight - 200, behavior: 'smooth' }); } catch(e){}
        });
      }
    },

    async saveEdit(spot, idx) {
      // prepare payload
      const payload = { status: this.editForm.status, number: this.editForm.number };
      try {
        const r = await this.$axios.put(`/admin/lots/${this.selectedLot.id}/spots/${spot.id}`, payload);
        // update local copy immutably using splice (Vue 3 friendly)
        const updated = r.data.spot || { ...spot, ...payload };
        // ensure number is string to keep consistent with backend
        updated.number = String(updated.number);
        this.spots.splice(idx, 1, updated);

        // clear editor state
        this.editingSpotId = null;
        this.editingIndex = null;
        this.editForm = { number: '', status: 'A', notes: '' };
      } catch (err) {
        console.error(err);
        alert(err?.response?.data?.error || "Failed to save spot");
      }
    },

    // -------------------------
    // NEW: Generate Monthly Reports
    // -------------------------
    async generateMonthlyReports() {
      if (!confirm('This will enqueue monthly reports generation for all users. Continue?')) return;
      this.generating = true;
      this.genTaskId = null;
      this.genStatus = null;

      try {
        const r = await this.$axios.post('/admin/generate-monthly-reports-now');
        this.genTaskId = r.data.task_id;
        this.genStatus = 'PENDING';
        this.startGenPoll();
      } catch (err) {
        console.error('Failed to enqueue monthly reports', err);
        alert(err?.response?.data?.error || err?.message || 'Failed to start reports');
      } finally {
        this.generating = false;
      }
    },

    startGenPoll() {
      if (this.genPollInterval) clearInterval(this.genPollInterval);
      this.genPollInterval = setInterval(this.pollGenStatus, 2000);
      this.pollGenStatus();
    },

    async pollGenStatus() {
      if (!this.genTaskId) return;
      try {
        const r = await this.$axios.get(`/export/status/${this.genTaskId}`);
        this.genStatus = r.data.state || r.data.status || 'UNKNOWN';

        if (['SUCCESS','FAILURE','REVOKED'].includes(this.genStatus)) {
          clearInterval(this.genPollInterval);
          this.genPollInterval = null;
        }
      } catch (err) {
        console.error('Gen status poll error', err);
        // keep trying a few times; do not spam if 404
      }
    },

    stopGenPoll() {
      if (this.genPollInterval) {
        clearInterval(this.genPollInterval);
        this.genPollInterval = null;
      }
    },

    // small helper for showing durations in spot details
    computeDuration(startIso, endIso) {
      if (!startIso) return '-';
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
        return '-';
      }
    }
  },
};
</script>

<style scoped>
.navbar .btn { min-width: 70px; }
</style>
