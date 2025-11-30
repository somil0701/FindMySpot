<template>
  <div class="container py-3">
    <h3 class="fw-bold mb-3">
      <i class="bi bi-people-fill text-primary me-2"></i>
      Admin — Manage Users
    </h3>

    <p class="text-muted mb-4">
      View all registered users. Delete users who no longer need accounts.
    </p>

    <div v-if="loading" class="text-center py-4">
      <div class="spinner-border text-primary"></div>
      <p class="mt-2">Loading users...</p>
    </div>

    <table v-if="!loading" class="table table-hover table-bordered align-middle shadow-sm">
      <thead class="table-light">
        <tr>
          <th>#</th>
          <th>Username</th>
          <th>Email</th>
          <th>Role</th>
          <th class="text-center" style="width:150px;">Actions</th>
        </tr>
      </thead>

      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.id }}</td>
          <td class="fw-semibold">{{ u.username }}</td>
          <td>{{ u.email }}</td>
          <td>
            <span class="badge" 
                  :class="u.role === 'admin' ? 'bg-dark' : 'bg-secondary'">
              {{ u.role }}
            </span>
          </td>
          <td class="text-center">

            <!-- View reservations -->
            <button 
              class="btn btn-sm btn-outline-primary me-2"
              @click="viewReservations(u)"
            >
              <i class="bi bi-clock-history"></i>
            </button>

            <!-- Delete user -->
            <button 
              v-if="u.role !== 'admin'"
              class="btn btn-sm btn-outline-danger"
              @click="deleteUser(u.id)"
            >
              <i class="bi bi-trash"></i>
            </button>

            <!-- Prevent deleting admin -->
            <span v-else class="text-muted small">Cannot delete admin</span>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- User reservation modal -->
    <div 
      v-if="showModal"
      class="modal-backdrop"
      @click="closeModal"
    >
      <div class="modal-dialog" @click.stop>
        <div class="modal-content p-3">

          <div class="d-flex justify-content-between align-items-center mb-2">
            <h5>User Reservations</h5>
            <button class="btn btn-sm btn-secondary" @click="closeModal">Close</button>
          </div>

          <div v-if="reservations.length === 0" class="text-muted">
            No reservations for this user.
          </div>

          <ul class="list-group">
            <li class="list-group-item" v-for="r in reservations" :key="r.id">
              <strong>Reservation #{{ r.id }}</strong><br>
              Lot: {{ r.lot_name }}<br>
              Spot: {{ r.spot_id }}<br>
              Start: {{ r.start_time }}<br>
              End: {{ r.end_time || 'Active' }}<br>
              Cost: ₹{{ r.cost || '-' }}
            </li>
          </ul>

        </div>
      </div>
    </div>

  </div>
</template>


<script>
import axios from "axios";

export default {
  name: "AdminUsersView",

  data() {
    return {
      users: [],
      loading: true,
      reservations: [],
      showModal: false,
    };
  },

  async mounted() {
    // Admin-only guard
    const user = JSON.parse(localStorage.getItem("user") || "null");
    if (!user || user.role !== "admin") {
      alert("Access denied: admin only.");
      this.$root.view = "Home";
      return;
    }

    await this.loadUsers();
  },

  methods: {
    async loadUsers() {
      this.loading = true;
      try {
        const res = await axios.get("/admin/users", {
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });

        this.users = res.data.users || [];
      } catch (err) {
        console.error("Failed to load users:", err);
        alert("Could not load users (admin only).");
      }
      this.loading = false;
    },

    async deleteUser(id) {
      if (!confirm("Are you sure you want to delete this user?")) return;

      try {
        const res = await axios.delete(`/admin/users/${id}`, {
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });

        alert("User deleted successfully.");
        await this.loadUsers();
      } catch (err) {
        console.error("Delete user failed:", err);
        alert(
          "Delete failed: " +
            (err.response?.data?.error || err.message || "Unknown error")
        );
      }
    },

    async viewReservations(user) {
      try {
        const res = await axios.get(`/admin/users/${user.id}/reservations`, {
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });
        this.reservations = res.data.reservations || [];
        this.showModal = true;
      } catch (err) {
        console.error("Failed to load reservations:", err);
        alert("Failed to load reservation history.");
      }
    },

    closeModal() {
      this.showModal = false;
      this.reservations = [];
    },
  },
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
}
.modal-dialog {
  max-width: 600px;
  width: 100%;
}
</style>
