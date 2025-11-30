<template>
  <div class="container py-4">
    <nav class="navbar navbar-expand-lg navbar-light mb-4 px-3 shadow-sm rounded-lg bg-white">
      <div class="container-fluid px-0">
        <a class="navbar-brand d-flex align-items-center gap-2" href="#" @click.prevent="set('Home')">
          <span class="brand-mark bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center">
            P
          </span>
          <div class="d-flex flex-column">
            <span class="fw-bold text-primary">ParkEZ</span>
            <small class="text-muted small">parking made easy</small>
          </div>
        </a>

        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNavbar"
          aria-controls="mainNavbar" aria-expanded="false" aria-label="Toggle navigation">
          <span class="navbar-toggler-icon"></span>
        </button>

        <div class="collapse navbar-collapse" id="mainNavbar">
          <ul class="navbar-nav ms-auto align-items-center gap-2">

            <!-- Primary navigation buttons -->
            <li class="nav-item">
              <button class="btn btn-outline-primary btn-sm px-3" @click="set('Home')">Home</button>
            </li>
            <li class="nav-item">
              <button class="btn btn-outline-secondary btn-sm px-3" @click="set('Lots')">Lots</button>
            </li>
            <li v-if="currentUser" class="nav-item">
              <button class="btn btn-outline-success btn-sm px-3" @click="set('UserDash')">My Parking</button>
            </li>
            <li v-if="currentUser" class="nav-item">
              <button class="btn btn-outline-info btn-sm px-3" @click="set('MyReports')">My Reports</button>
            </li>
            <li v-if="currentUser" class="nav-item">
              <button class="btn btn-outline-info btn-sm px-3" @click="set('UserHistory')">History</button>
            </li>

            <!-- Admin Panel button (left-side) -->
            <li v-if="currentUser && currentUser.role === 'admin'" class="nav-item">
              <div class="btn-group">
                <button class="btn btn-dark btn-sm px-3" @click="set('Admin')">
                  Admin Panel
                </button>
                <button type="button" class="btn btn-dark btn-sm dropdown-toggle dropdown-toggle-split"
                        data-bs-toggle="dropdown" aria-expanded="false">
                  <span class="visually-hidden">Toggle admin menu</span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end">
                  <li><a class="dropdown-item" href="#" @click.prevent="set('Admin')">Manage Lots</a></li>
                  <li><a class="dropdown-item" href="#" @click.prevent="set('AdminUsers')">Manage Users</a></li>
                  <li><a class="dropdown-item" href="#" @click.prevent="set('AdminAnalytics')">Analytics</a></li>
                  <li><hr class="dropdown-divider"></li>

                  <!-- QUICK ACTIONS -->
                  <li>
                    <a class="dropdown-item" href="#" @click.prevent="triggerDailyReminder">
                      Send Daily Reminder (now)
                    </a>
                  </li>
                  <li>
                    <a class="dropdown-item" href="#" @click.prevent="triggerMonthlyReportsNow">
                      Generate Monthly Reports (now)
                    </a>
                  </li>
                </ul>
              </div>
            </li>

            <!-- Auth buttons when not logged in -->
            <li v-if="!currentUser" class="nav-item">
              <button class="btn btn-primary btn-sm" @click="set('Login')">Login</button>
            </li>
            <li v-if="!currentUser" class="nav-item">
              <button class="btn btn-outline-secondary btn-sm" @click="set('Register')">Register</button>
            </li>

            <!-- Rightmost: user dropdown (logged in user) -->
            <li v-if="currentUser" class="nav-item dropdown ms-2">
              <a class="nav-link d-flex align-items-center gap-2" href="#" id="userMenu" role="button"
                 data-bs-toggle="dropdown" aria-expanded="false">
                <span class="user-avatar bg-light text-dark rounded-circle d-inline-flex align-items-center justify-content-center">
                  {{ currentUser.username ? currentUser.username.charAt(0).toUpperCase() : '?' }}
                </span>
                <span class="d-none d-md-inline small text-dark">{{ currentUser.username }}</span>
                <i class="bi bi-caret-down-fill small text-muted ms-1"></i>
              </a>

              <ul class="dropdown-menu dropdown-menu-end shadow-sm" aria-labelledby="userMenu">
                <li><a class="dropdown-item" href="#" @click.prevent="set('UserDash')">Dashboard</a></li>
                <li><a class="dropdown-item" href="#" @click.prevent="set('UserHistory')">History</a></li>
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item text-danger" href="#" @click.prevent="logout">Logout</a></li>
              </ul>
            </li>

          </ul>
        </div>
      </div>
    </nav>

    <!-- Dynamic view renderer -->
    <component :is="currentView"></component>
  </div>
</template>

<script>
import UserHistoryView from "./views/UserHistoryView.vue";
import AdminUsersView from "./views/AdminUsersView.vue";
import HomeView from "./views/HomeView.vue";
import LotsView from "./views/LotsView.vue";
import AdminLotsView from "./views/AdminLotsView.vue";
import AdminAnalytics from "./views/AdminAnalytics.vue";
import UserDashboard from "./views/UserDashboard.vue";
import LoginView from "./views/LoginView.vue";
import RegisterView from "./views/RegisterView.vue";
import MyReports from "./views/MyReports.vue";

export default {
  name: "App",

  data() {
    return {
      view: "Home",
      userState: JSON.parse(localStorage.getItem("user") || "null"),
      // prevent double-clicking during requests
      adminActionPending: false
    };
  },

  computed: {
    currentView() {
      return {
        Home: HomeView,
        Lots: LotsView,
        UserDash: UserDashboard,
        UserHistory: UserHistoryView,
        Admin: AdminLotsView,
        AdminUsers: AdminUsersView,
        AdminAnalytics: AdminAnalytics,
        Login: LoginView,
        Register: RegisterView,
        MyReports: MyReports,
      }[this.view] || HomeView;
    },
    currentUser() {
      return this.userState;
    },
  },

  methods: {
    set(v) {
      if (v === "Admin" || v === "AdminUsers" || v === "AdminAnalytics") {
        if (!this.currentUser || this.currentUser.role !== "admin") {
          alert("Access denied: admin only.");
          return;
        }
      }
      this.view = v;
    },

    logout() {
      localStorage.removeItem("user");
      localStorage.removeItem("token");
      if (this.$axios && this.$axios.defaults && this.$axios.defaults.headers) {
        delete this.$axios.defaults.headers.common["Authorization"];
      } else if (typeof window !== "undefined" && window.axios && window.axios.defaults) {
        delete window.axios.defaults.headers.common["Authorization"];
      }
      this.userState = null;
      window.dispatchEvent(new Event("user-changed"));
      this.view = "Login";
      alert("Logged out.");
    },

    onUserChanged() {
      try {
        this.userState = JSON.parse(localStorage.getItem("user") || "null");
      } catch (e) {
        this.userState = null;
      }
      if (this.userState) {
        if (this.view === "Login" || this.view === "Register") {
          this.view = "UserDash";
        }
      }
    },

    // -------------------------
    // Admin quick actions
    // -------------------------
    async triggerDailyReminder() {
      if (!this.currentUser || this.currentUser.role !== 'admin') { alert('Admin only'); return; }
      if (this.adminActionPending) return;
      if (!confirm('Send daily reminders now to eligible users?')) return;

      this.adminActionPending = true;
      try {
        const resp = await (this.$axios ? this.$axios : window.axios).post('/admin/send-daily-reminder', { cutoff_days: 7 });
        alert('Daily reminder enqueued. Task id: ' + (resp.data?.task_id || 'unknown'));
        console.log('triggerDailyReminder response', resp.data);
      } catch (err) {
        console.error('Daily reminder failed:', err);
        alert(err?.response?.data?.message || err?.response?.data?.error || err?.message || 'Failed to enqueue daily reminders');
      } finally {
        this.adminActionPending = false;
      }
    },

    async triggerMonthlyReportsNow() {
      if (!this.currentUser || this.currentUser.role !== 'admin') { alert('Admin only'); return; }
      if (this.adminActionPending) return;
      if (!confirm('Enqueue monthly reports for all users now?')) return;

      this.adminActionPending = true;
      try {
        const resp = await (this.$axios ? this.$axios : window.axios).post('/admin/generate-monthly-reports-now');
        alert('Monthly reports enqueued. Task id: ' + (resp.data?.task_id || 'unknown'));
        console.log('triggerMonthlyReportsNow response', resp.data);
      } catch (err) {
        console.error('Monthly reports enqueue failed:', err);
        alert(err?.response?.data?.message || err?.response?.data?.error || err?.message || 'Failed to enqueue monthly reports');
      } finally {
        this.adminActionPending = false;
      }
    }
  },

  mounted() {
    const token = localStorage.getItem("token");
    if (token) {
      if (this.$axios && this.$axios.defaults && this.$axios.defaults.headers) {
        this.$axios.defaults.headers.common["Authorization"] = "Bearer " + token;
      } else {
        if (typeof window !== "undefined" && window.axios && window.axios.defaults) {
          window.axios.defaults.headers.common["Authorization"] = "Bearer " + token;
        }
      }
    }
    window.addEventListener("user-changed", this.onUserChanged);
  },

  beforeUnmount() {
    window.removeEventListener("user-changed", this.onUserChanged);
  }
};
</script>

<style scoped>
.brand-mark {
  width:40px;
  height:40px;
  font-weight:700;
  font-size:18px;
}
.user-avatar {
  width:36px;
  height:36px;
  border-radius:50%;
  font-weight:600;
  font-size:14px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
}
.navbar .btn { min-width: 70px; }
@media (max-width: 575px) {
  .user-avatar + .small { display:none; }
}
</style>
