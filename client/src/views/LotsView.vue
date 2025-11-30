<template>
  <div>
    <h3 class="mb-3">Available Parking Lots</h3>

    <div class="row">
      <div class="col-md-4" v-for="lot in lots" :key="lot.id">
        <div class="card shadow-sm mb-3">
          <div class="card-body">
            <h5 class="card-title">{{ lot.name }}</h5>
            <small class="text-muted">{{ lot.address }}</small>

            <p class="mt-2 mb-1">Price/hr: <strong>{{ lot.price_per_hour }}</strong></p>
            <p class="mb-2">Capacity: {{ lot.capacity }}</p>

            <button class="btn btn-success btn-sm" @click="reserve(lot.id)">
              Reserve Spot
            </button>

          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return { lots: [] };
  },

  mounted() {
    this.load();
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

    async reserve(lot_id) {
       const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "null");

  if (!token || !user) {
    alert("Please log in first.");
    return;
  }

  // Ask user for optional notes/remarks before reserving
  const notes = prompt("Add notes/remarks for this reservation (optional):", "") || null;

  try {
    const r = await this.$axios.post("/user/reserve", { lot_id, notes });
    const spotNumber = r?.data?.spot?.number || "unknown";
    alert("Reserved spot: " + spotNumber);
    this.load();
  } catch (e) {
    const msg = e?.response?.data?.error || e?.response?.data?.message || "Failed to reserve.";
    alert(msg);
  }
    },
  },
};
</script>
