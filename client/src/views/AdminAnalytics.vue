<template>
  <div class="container py-4">
    <h2 class="mb-4">📊 Parking Analytics Dashboard</h2>

    <div class="row g-4">

      <!-- Occupancy Chart -->
      <div class="col-lg-6">
        <div class="card shadow-sm">
          <div class="card-header bg-primary text-white">Occupancy per Lot</div>
          <div class="card-body">
            <canvas id="chartOccupancy"></canvas>
          </div>
        </div>
      </div>

      <!-- Revenue Chart -->
      <div class="col-lg-6">
        <div class="card shadow-sm">
          <div class="card-header bg-success text-white">Revenue per Lot</div>
          <div class="card-body">
            <canvas id="chartRevenue"></canvas>
          </div>
        </div>
      </div>

      <!-- 30 Day Trend -->
      <div class="col-12">
        <div class="card shadow-sm">
          <div class="card-header bg-warning">Reservations Last 30 Days</div>
          <div class="card-body">
            <canvas id="chartTrend"></canvas>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script>
import axios from "axios";
import Chart from "chart.js/auto";

export default {
  data() {
    return {
      analytics: null,
    };
  },

  async mounted() {
    await this.loadAnalytics();
    this.renderCharts();
  },

  methods: {
    async loadAnalytics() {
      const res = await axios.get("/admin/analytics/summary", {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      this.analytics = res.data;
    },

    renderCharts() {
      if (!this.analytics) return;

      // Occupancy Chart
      const occLabels = this.analytics.occupancy.map(o => o.lot_name);
      const occOccupied = this.analytics.occupancy.map(o => o.occupied);
      const occAvailable = this.analytics.occupancy.map(o => o.available);

      new Chart(document.getElementById("chartOccupancy"), {
        type: "bar",
        data: {
          labels: occLabels,
          datasets: [
            { label: "Occupied", data: occOccupied, backgroundColor: "rgba(255, 99, 132, 0.6)" },
            { label: "Available", data: occAvailable, backgroundColor: "rgba(75, 192, 192, 0.6)" }
          ]
        }
      });

      // Revenue per Lot
      const revLabels = this.analytics.revenue_per_lot.map(r => r.lot_name);
      const revData = this.analytics.revenue_per_lot.map(r => r.revenue);

      new Chart(document.getElementById("chartRevenue"), {
        type: "bar",
        data: {
          labels: revLabels,
          datasets: [
            { label: "Revenue", data: revData, backgroundColor: "rgba(54, 162, 235, 0.6)" }
          ]
        }
      });

      // 30-Day Trend
      const dates = this.analytics.reservations_last_30_days.map(d => d.date);
      const counts = this.analytics.reservations_last_30_days.map(d => d.count);

      new Chart(document.getElementById("chartTrend"), {
        type: "line",
        data: {
          labels: dates,
          datasets: [
            {
              label: "Reservations",
              data: counts,
              borderColor: "rgba(255, 159, 64, 0.8)",
              fill: false,
              tension: 0.2
            }
          ]
        }
      });
    }
  }
};
</script>

<style>
.card {
  border-radius: 12px;
}
</style>
