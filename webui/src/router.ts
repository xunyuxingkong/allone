import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import RunListView from './views/RunListView.vue'
import RunDetailView from './views/RunDetailView.vue'
import CaseDetailView from './views/CaseDetailView.vue'
import RuntimeView from './views/RuntimeView.vue'
import CoverageView from './views/CoverageView.vue'
import CandidateListView from './views/CandidateListView.vue'
import CandidateDetailView from './views/CandidateDetailView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/runs', name: 'runs', component: RunListView },
    { path: '/runs/:runId', name: 'run-detail', component: RunDetailView, props: true },
    { path: '/runs/:runId/cases/:caseId', name: 'case-detail', component: CaseDetailView, props: true },
    { path: '/runtime', name: 'runtime', component: RuntimeView },
    { path: '/coverage', name: 'coverage', component: CoverageView },
    { path: '/candidates', name: 'candidates', component: CandidateListView },
    { path: '/candidates/:caseId', name: 'candidate-detail', component: CandidateDetailView, props: true },
  ],
})
