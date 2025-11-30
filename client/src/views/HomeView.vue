<template>
  <div>
    <div class="card p-4 mb-4">
      <div class="row g-0 align-items-center">
        <div class="col-md-6 pe-3">
          <h1 class="fw-bold text-primary mb-2">ParkEZ</h1>
          <p class="lead small-muted mb-3">A fast, simple, and reliable vehicle parking reservation system.</p>

          <div class="d-flex gap-2">
            <button class="btn btn-primary" @click="$root.view = 'Lots'">Explore Lots</button>
            <button class="btn btn-outline-secondary" @click="$root.view = 'Register'">Register</button>
          </div>
        </div>

        <div class="col-md-6">
          <img src="https://picsum.photos/900/300" alt="cover" class="hero-img ms-md-3" />
        </div>
      </div>
    </div>

    <div class="row">
      <div class="col-md-4">
        <div class="card p-3 mb-3">
          <h6 class="mb-1">Quick stats</h6>
          <p class="small-muted mb-0">View lots, reserve a spot and check your history.</p>
        </div>
      </div>

      <div class="col-md-4">
        <div class="card p-3 mb-3">
          <h6 class="mb-1">Secure</h6>
          <p class="small-muted mb-0">Role based access and secure tokens.</p>
        </div>
      </div>

      <div class="col-md-4">
        <div class="card p-3 mb-3">
          <h6 class="mb-1">Exports</h6>
          <p class="small-muted mb-0">Generate CSV and monthly reports with one click.</p>
        </div>
      </div>
    </div>
  </div>
</template>
