<template>
  <div class="as-shell">
    <header class="as-header">
      <div class="brand">
        <span class="brand-mark"></span>
        <h1>Audience Studio</h1>
      </div>
      <p class="muted tagline">
        A calibrated simulation layer on top of reach and ratings. Load a study,
        run the simulation, read the results.
      </p>
      <nav class="stage-strip" aria-label="Stage progress">
        <a href="#stage-load"  class="strip" :class="{ active: activeStage === 'load' }">
          <span class="strip-num">1</span> Load
        </a>
        <span class="strip-sep" aria-hidden="true">›</span>
        <a href="#stage-sim"   class="strip" :class="{ active: activeStage === 'sim' }">
          <span class="strip-num">2</span> Simulation
        </a>
        <span class="strip-sep" aria-hidden="true">›</span>
        <a href="#stage-res"   class="strip" :class="{ active: activeStage === 'res' }">
          <span class="strip-num">3</span> Results
        </a>
      </nav>
    </header>

    <!-- ============= STAGE 1 — LOAD ============= -->
    <section id="stage-load" class="stage stage-load" ref="stageLoadEl">
      <div class="stage-head">
        <span class="stage-num">1</span>
        <div>
          <h2 class="stage-title">Load</h2>
          <p class="stage-sub">Upload or register a study, then browse its universe before running.</p>
        </div>
      </div>
      <div class="stage-body">
        <div class="row">
          <label class="file-pick">
            <input type="file" accept=".zip,.json" @change="onFilePicked" />
            <span>Choose study (.zip with study.json + CSVs, or bare study.json)</span>
          </label>
          <button :disabled="!pickedFile || uploading" @click="uploadPicked">
            {{ uploading ? 'Uploading…' : 'Upload study' }}
          </button>
        </div>
        <p v-if="pickedFile" class="muted small">Picked: {{ pickedFile.name }} ({{ humanSize(pickedFile.size) }})</p>
        <p v-if="uploadError" class="error">{{ uploadError }}</p>
        <p v-if="uploadOk" class="ok small">
          Uploaded <code>{{ uploadOk.study_id }}</code> at {{ uploadOk.registered_at }}
          <span v-if="uploadOk.suffixed">
            (the file&rsquo;s study_id collided with an existing entry, so it was
            registered under a suffixed id — both rows are now selectable)
          </span>
        </p>

        <details class="from-disk">
          <summary>or register a server-side path</summary>
          <div class="row">
            <input
              v-model="newStudyPath"
              type="text"
              placeholder="seeds/v2/bbc_panel/study.json"
              class="grow"
            />
            <button :disabled="!newStudyPath || registering" @click="registerStudy">
              {{ registering ? 'Registering…' : 'Register from path' }}
            </button>
          </div>
          <p v-if="registerError" class="error">{{ registerError }}</p>
        </details>

        <table v-if="studies.length" class="grid">
          <thead>
            <tr>
              <th></th>
              <th>study_id</th>
              <th>name</th>
              <th>identities</th>
              <th>edges</th>
              <th>brief</th>
              <th>registered</th>
              <th>actions</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in studies" :key="s.study_id"
                :class="{ selected: selectedStudyId === s.study_id }"
                @click="selectedStudyId = s.study_id">
              <td>
                <input type="radio"
                       :value="s.study_id"
                       v-model="selectedStudyId"
                       :name="'pick-study'" />
              </td>
              <td><code>{{ s.study_id }}</code></td>
              <td>{{ s.name }}</td>
              <td>{{ s.panelists }}</td>
              <td>{{ s.edges }}</td>
              <td>{{ s.brief.title }} <span class="muted small">({{ s.brief.air_date }})</span></td>
              <td class="muted small">{{ s.registered_at || '—' }}</td>
              <td class="action-cell">
                <button class="ghost primary"
                        @click.stop="openInspector(s.study_id)">View</button>
                <a :href="`/api/v2/studies/${s.study_id}/json`"
                   :download="`${s.study_id}.json`"
                   class="link"
                   @click.stop>study.json</a>
                <a :href="`/api/v2/studies/${s.study_id}/bundle`"
                   :download="`${s.study_id}.zip`"
                   class="link"
                   @click.stop>.zip</a>
              </td>
              <td>
                <button class="ghost danger"
                        :disabled="deletingId === s.study_id"
                        @click.stop="onDeleteStudy(s)">
                  {{ deletingId === s.study_id ? 'Deleting…' : 'Delete' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">No studies registered yet.</p>

        <!-- Universe — graph of the selected study -->
        <div v-if="selectedStudyId" class="universe">
          <div class="universe-head">
            <h3 class="sub-h">
              <span class="universe-eyebrow">Universe</span>
              The behavioural model behind <code>{{ selectedStudyId }}</code>
            </h3>
            <button v-if="!graphLoading"
                    class="ghost primary"
                    @click="onBuildGraph">
              {{ buildingGraph
                ? 'Building…'
                : graphMissing
                  ? 'Build graph'
                  : graphData
                    ? 'Rebuild graph'
                    : 'Load graph' }}
            </button>
          </div>

          <p v-if="graphLoading" class="muted small">Loading graph…</p>
          <p v-if="graphMissing && !buildingGraph && !graphData" class="muted small">
            No graph in Neo4j for this study yet. Click <strong>Build graph</strong> above to materialise it,
            or it will be written automatically the next time you run.
          </p>
          <p v-if="graphError" class="error">{{ graphError }}</p>

          <template v-if="graphData && graphData.nodes && graphData.nodes.length">
            <p class="muted small">
              {{ graphData.node_count }} nodes, {{ graphData.edge_count }} edges across
              {{ legendLabels.length }} node types. Drag to rearrange · click a node to inspect.
            </p>
            <div class="graph-legend">
              <span v-for="lbl in legendLabels" :key="lbl"
                    class="legend-pill" :data-lbl="lbl"
                    :style="legendStyle(lbl)">{{ lbl }}</span>
            </div>
            <div class="graph-flex">
              <svg ref="graphSvg" class="graph-svg" :width="graphWidth" :height="graphHeight"></svg>
              <aside class="node-panel">
                <div v-if="!selectedNode" class="muted small">
                  Click any node to inspect its attributes and edges.
                </div>
                <div v-else>
                  <div class="node-head">
                    <span class="legend-pill"
                          :data-lbl="selectedNode.label"
                          :style="legendStyle(selectedNode.label)">{{ selectedNode.label }}</span>
                    <code>{{ selectedNode.key }}</code>
                  </div>
                  <h4 v-if="selectedNode.props && (selectedNode.props.name || selectedNode.props.title)">
                    {{ selectedNode.props.name || selectedNode.props.title }}
                  </h4>
                  <table class="props">
                    <tbody>
                      <tr v-for="(v, k) in flatProps(selectedNode.props)" :key="k">
                        <th>{{ k }}</th>
                        <td><pre>{{ v }}</pre></td>
                      </tr>
                    </tbody>
                  </table>
                  <h5 v-if="selectedEdges.length">Edges ({{ selectedEdges.length }})</h5>
                  <ul class="edge-list">
                    <li v-for="(e, i) in selectedEdges" :key="i">
                      <code>{{ e.dir }}</code>
                      <span class="etype">{{ e.type }}</span>
                      <code>{{ e.otherLabel }}:{{ e.otherKey }}</code>
                      <span v-if="e.props && Object.keys(e.props).length" class="muted small">
                        {{ JSON.stringify(e.props) }}
                      </span>
                    </li>
                  </ul>
                </div>
              </aside>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- ============= STAGE 2 — SIMULATION ============= -->
    <section id="stage-sim" class="stage stage-sim" ref="stageSimEl">
      <div class="stage-head">
        <span class="stage-num">2</span>
        <div>
          <h2 class="stage-title">Simulation</h2>
          <p class="stage-sub">Configure rounds, kick off the run, watch the engagement gate decide who reacts.</p>
        </div>
      </div>
      <div class="stage-body">
        <div class="selected-bar">
          <template v-if="selectedStudy">
            <span class="lbl">Selected</span>
            <strong>{{ selectedStudy.name }}</strong>
            <code>{{ selectedStudy.study_id }}</code>
            <span class="muted">·  {{ selectedStudy.panelists }} identities · {{ selectedStudy.edges }} edges</span>
          </template>
          <template v-else>
            <span class="muted">Pick a study in Stage 1 (radio in the table).</span>
          </template>
        </div>

        <div class="row">
          <label>Rounds
            <input v-model.number="rounds" type="number" min="1" max="5" class="narrow" />
          </label>
          <label class="checkbox">
            <input v-model="skipNeo4j" type="checkbox" /> skip Neo4j
          </label>
          <label class="checkbox">
            <input v-model="noLlmNarrator" type="checkbox" /> deterministic narrator (no LLM)
          </label>
          <button :disabled="!selectedStudyId || running" @click="kickOffRun">
            {{ running ? 'Running…' : 'Run simulation' }}
          </button>
        </div>
        <p v-if="runError" class="error">{{ runError }}</p>

        <div v-if="activeRun" class="run-status">
          <div class="run-head">
            <span class="run-id">run <code>{{ activeRun.run_id }}</code></span>
            <span class="run-step">
              <strong>{{ activeRun.status }}</strong>
              — step {{ activeRun.step }} / {{ activeRun.step_total }}
            </span>
            <span class="downloads">
              <a :href="`/api/v2/studies/${activeRun.study_id}/json`"
                 :download="`${activeRun.study_id}.json`"
                 class="link">study.json</a>
              <a :href="`/api/v2/studies/${activeRun.study_id}/bundle`"
                 :download="`${activeRun.study_id}.zip`"
                 class="link">.zip</a>
            </span>
          </div>
          <pre class="log">{{ logText }}</pre>
        </div>
      </div>
    </section>

    <!-- ============= STAGE 3 — RESULTS ============= -->
    <section id="stage-res" class="stage stage-res" ref="stageResEl">
      <div class="stage-head">
        <span class="stage-num">3</span>
        <div>
          <h2 class="stage-title">Results</h2>
          <p class="stage-sub">Headline metrics and the narrative report. Universe view is up in Stage 1.</p>
        </div>
      </div>
      <div class="stage-body">
        <div v-if="!activeRun" class="muted placeholder">
          Run a simulation in Stage 2 to see results here.
        </div>

        <div v-if="activeRun?.headline" class="headline">
          <span><strong>reach</strong> {{ activeRun.headline.reach }}/{{ activeRun.headline.panel_size }}</span>
          <span><strong>engagement</strong> {{ activeRun.headline.engagement }}/{{ activeRun.headline.panel_size }}</span>
          <span><strong>appreciation index</strong> {{ aiStr(activeRun.headline.appreciation_index) }}</span>
          <span><strong>clarity risk</strong> {{ activeRun.headline.clarity_risk }}/{{ activeRun.headline.panel_size }}</span>
        </div>

        <div v-if="reportHtml" class="report-wrap">
          <h3 class="sub-h">Report</h3>
          <div class="report-html" v-html="reportHtml"></div>
        </div>
      </div>
    </section>

    <StudyInspector
      :open="inspectorOpen"
      :study-id="inspectorStudyId"
      @close="inspectorOpen = false"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { marked } from 'marked'
import {
  buildStudyGraph,
  deleteStudy,
  getGraph,
  getRun,
  getRunLog,
  getRunReportMarkdown,
  listStudies,
  registerStudyFromDisk,
  startRun,
  uploadStudy
} from '../api/v2'
import StudyInspector from '../components/StudyInspector.vue'

const studies = ref([])
const selectedStudyId = ref('')
const newStudyPath = ref('seeds/v2/bbc_panel/study.json')
const pickedFile = ref(null)

const registering = ref(false)
const registerError = ref('')
const uploading = ref(false)
const uploadError = ref('')
const uploadOk = ref(null)
const deletingId = ref('')

const running = ref(false)
const runError = ref('')

const activeRun = ref(null)
const reportMarkdown = ref('')
const graphData = ref(null)
const graphError = ref('')
const graphLoading = ref(false)
const graphMissing = ref(false)
const buildingGraph = ref(false)
const graphSvg = ref(null)
const graphWidth = 720
const graphHeight = 540
const selectedNode = ref(null)
let pollHandle = null
let simulation = null

// Inspector
const inspectorOpen = ref(false)
const inspectorStudyId = ref('')

// Stage indicator
const activeStage = ref('load')
const stageLoadEl = ref(null)
const stageSimEl  = ref(null)
const stageResEl  = ref(null)
let stageObserver = null

// ---------- node label palette ----------
const LABEL_COLOR = {
  Panelist:           '#2563eb',
  Genre:              '#65a30d',
  Slot:               '#b45309',
  Brief:              '#be185d',
  Region:             '#0d9488',
  HouseholdType:      '#7c3aed',
  VoiceRegister:      '#e11d48',
  ClaritySensitivity: '#0891b2',
  Gender:             '#475569',
  AgeBand:            '#ea580c'
}
const LABEL_RADIUS = {
  Brief:              14,
  Panelist:           12,
  Region:             9,
  HouseholdType:      9,
  Genre:              8,
  Slot:               8,
  VoiceRegister:      8,
  ClaritySensitivity: 8,
  Gender:             8,
  AgeBand:            8
}

const legendLabels = computed(() => {
  if (!graphData.value?.nodes) return []
  const set = new Set()
  for (const n of graphData.value.nodes) set.add(n.label)
  // Stable ordering
  const order = ['Panelist','Region','HouseholdType','VoiceRegister','ClaritySensitivity','Gender','AgeBand','Genre','Slot','Brief']
  return order.filter(l => set.has(l)).concat([...set].filter(l => !order.includes(l)))
})

function legendStyle(label) {
  const c = LABEL_COLOR[label]
  return c ? { '--lbl-color': c } : {}
}

// ---------- computed ----------
const logText = computed(() => (activeRun.value?.log || []).join('\n'))
const selectedStudy = computed(() =>
  studies.value.find(s => s.study_id === selectedStudyId.value) || null
)
const reportHtml = computed(() => {
  if (!reportMarkdown.value) return ''
  try {
    return marked.parse(reportMarkdown.value, { gfm: true, breaks: false })
  } catch {
    return `<pre>${escapeHtml(reportMarkdown.value)}</pre>`
  }
})
function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const selectedEdges = computed(() => {
  if (!selectedNode.value || !graphData.value) return []
  const id = selectedNode.value.id
  const byId = new Map(graphData.value.nodes.map(n => [n.id, n]))
  const out = []
  for (const e of graphData.value.edges) {
    if (e.source === id) {
      const other = byId.get(e.target)
      out.push({ dir: '→', type: e.type, otherLabel: other?.label, otherKey: other?.key, props: e.props })
    } else if (e.target === id) {
      const other = byId.get(e.source)
      out.push({ dir: '←', type: e.type, otherLabel: other?.label, otherKey: other?.key, props: e.props })
    }
  }
  return out
})

function aiStr(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(1)
}
function humanSize(n) {
  if (!n && n !== 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}
function flatProps(p) {
  if (!p) return {}
  const out = {}
  for (const [k, v] of Object.entries(p)) {
    if (k.startsWith('_') && k !== '_key') continue
    out[k] = typeof v === 'object' && v !== null ? JSON.stringify(v, null, 2) : v
  }
  return out
}

function openInspector(study_id) {
  inspectorStudyId.value = study_id
  inspectorOpen.value = true
}

async function onDeleteStudy(s) {
  if (!s || !s.study_id) return
  if (!window.confirm(`Delete study "${s.study_id}"? Run history is kept; only the registered study and its uploaded files are removed.`)) return
  deletingId.value = s.study_id
  try {
    await deleteStudy(s.study_id)
    if (selectedStudyId.value === s.study_id) selectedStudyId.value = ''
    await refreshStudies()
  } catch (err) {
    window.alert('Delete failed: ' + String(err?.response?.data?.error || err?.message || err))
  } finally {
    deletingId.value = ''
  }
}

async function refreshStudies() {
  try {
    const res = await listStudies()
    studies.value = res.data || []
    if (!selectedStudyId.value && studies.value.length) {
      selectedStudyId.value = studies.value[0].study_id
    }
  } catch (err) {
    console.error('listStudies failed', err)
  }
}

function onFilePicked(ev) {
  uploadError.value = ''
  pickedFile.value = ev.target.files && ev.target.files[0] ? ev.target.files[0] : null
}

async function uploadPicked() {
  if (!pickedFile.value) return
  uploadError.value = ''
  uploadOk.value = null
  uploading.value = true
  try {
    const res = await uploadStudy(pickedFile.value)
    const rec = res && res.data
    if (rec && rec.study_id) {
      selectedStudyId.value = rec.study_id
      uploadOk.value = {
        study_id:      rec.study_id,
        registered_at: rec.registered_at,
        suffixed:      /__\d+$/.test(rec.study_id),
      }
    }
    pickedFile.value = null
    await refreshStudies()
  } catch (err) {
    uploadError.value = String(err?.response?.data?.error || err?.message || err)
  } finally {
    uploading.value = false
  }
}

async function registerStudy() {
  registerError.value = ''
  registering.value = true
  try {
    const res = await registerStudyFromDisk(newStudyPath.value.trim())
    if (res && res.data && res.data.study_id) {
      selectedStudyId.value = res.data.study_id
    }
    await refreshStudies()
  } catch (err) {
    registerError.value = String(err?.response?.data?.error || err?.message || err)
  } finally {
    registering.value = false
  }
}

const rounds = ref(2)
const skipNeo4j = ref(false)
const noLlmNarrator = ref(false)

async function kickOffRun() {
  runError.value = ''
  running.value = true
  reportMarkdown.value = ''
  try {
    const res = await startRun({
      study_id: selectedStudyId.value,
      rounds: rounds.value,
      skip_neo4j: skipNeo4j.value,
      no_llm_narrator: noLlmNarrator.value
    })
    activeRun.value = res.data
    pollUntilDone()
  } catch (err) {
    runError.value = String(err?.message || err)
    running.value = false
  }
}

async function pollUntilDone() {
  if (!activeRun.value) return
  const id = activeRun.value.run_id
  pollHandle = setInterval(async () => {
    try {
      const [statusRes, logRes] = await Promise.all([getRun(id), getRunLog(id)])
      activeRun.value = { ...statusRes.data, log: logRes.data || [] }
      if (activeRun.value.status === 'done') {
        clearInterval(pollHandle)
        pollHandle = null
        running.value = false
        const md = await getRunReportMarkdown(id)
        reportMarkdown.value = md
        // Refresh graph after run in case it was newly written
        await loadAndRenderGraph(activeRun.value.study_id)
      } else if (activeRun.value.status === 'failed') {
        clearInterval(pollHandle)
        pollHandle = null
        running.value = false
        runError.value = activeRun.value.error || 'run failed'
      }
    } catch (err) {
      console.error('poll error', err)
    }
  }, 2000)
}

async function loadAndRenderGraph(study_id) {
  if (!study_id) return
  graphError.value = ''
  graphMissing.value = false
  graphData.value = null
  selectedNode.value = null
  graphLoading.value = true
  try {
    const graph_id = `v2_${study_id}`
    const res = await getGraph(graph_id)
    const data = res.data
    if (!data || !data.nodes || data.nodes.length === 0) {
      graphMissing.value = true
      graphData.value = null
      return
    }
    graphData.value = data
    await nextTick()
    renderGraph(data)
  } catch (err) {
    graphError.value =
      'Could not load graph from Neo4j. ' +
      'On Railway, this happens when the graphdb service is offline.'
  } finally {
    graphLoading.value = false
  }
}

async function onBuildGraph() {
  if (!selectedStudyId.value) return
  graphError.value = ''
  buildingGraph.value = true
  try {
    await buildStudyGraph(selectedStudyId.value)
    await loadAndRenderGraph(selectedStudyId.value)
  } catch (err) {
    graphError.value =
      'Build graph failed: ' +
      String(err?.response?.data?.error || err?.message || err)
  } finally {
    buildingGraph.value = false
  }
}

function renderGraph(data) {
  if (simulation) simulation.stop()
  const svg = d3.select(graphSvg.value)
  svg.selectAll('*').remove()

  const width = graphWidth
  const height = graphHeight

  const links = data.edges.map(e => ({
    source: e.source,
    target: e.target,
    type: e.type,
    propensity: e.props && e.props.propensity ? e.props.propensity : 0.5
  }))
  const nodes = data.nodes.map(n => ({
    id: n.id,
    label: n.label,
    key: n.key,
    raw: n,
    name: (n.props && (n.props.name || n.props.title)) || n.key
  }))

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id)
      .distance(d => 55 + (1 - (d.propensity || 0.5)) * 70)
      .strength(d => 0.2 + (d.propensity || 0.5) * 0.55))
    .force('charge', d3.forceManyBody().strength(-260))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => (LABEL_RADIUS[d.label] || 9) + 5))

  const link = svg.append('g')
    .attr('stroke', '#cbd5e1')
    .selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke-width', d => 0.5 + (d.propensity || 0.5) * 2.0)
    .attr('stroke-opacity', d => 0.22 + (d.propensity || 0.5) * 0.5)

  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .enter().append('g')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      selectedNode.value = d.raw
      svg.selectAll('g.node-group circle').attr('stroke-width', 1.5)
      d3.select(event.currentTarget).select('circle').attr('stroke-width', 3.5)
    })
    .attr('class', 'node-group')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null; d.fy = null
      }))

  node.append('circle')
    .attr('r', d => LABEL_RADIUS[d.label] || 8)
    .attr('fill', d => LABEL_COLOR[d.label] || '#6b7280')
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)

  node.append('title')
    .text(d => `${d.label}: ${d.name}`)

  node.append('text')
    .text(d => d.label === 'Panelist'
      ? d.name.split(' ')[0]
      : (d.key || '').toString().replace(/_/g, ' '))
    .attr('x', d => (LABEL_RADIUS[d.label] || 8) + 4)
    .attr('y', 4)
    .attr('font-size', 11)
    .attr('fill', '#1f2937')

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    node.attr('transform', d => `translate(${d.x},${d.y})`)
  })
}

function setupStageObserver() {
  const map = new Map([
    [stageLoadEl.value, 'load'],
    [stageSimEl.value,  'sim'],
    [stageResEl.value,  'res']
  ])
  stageObserver = new IntersectionObserver((entries) => {
    let best = null
    for (const e of entries) {
      if (!e.isIntersecting) continue
      if (!best || e.intersectionRatio > best.intersectionRatio) best = e
    }
    if (best) {
      const tag = map.get(best.target)
      if (tag) activeStage.value = tag
    }
  }, { threshold: [0.2, 0.4, 0.6] })
  for (const el of map.keys()) {
    if (el) stageObserver.observe(el)
  }
}

// Reactively load the graph when the user picks a study (or after a run).
watch(selectedStudyId, async (id) => {
  if (!id) {
    graphData.value = null
    graphError.value = ''
    graphMissing.value = false
    return
  }
  await loadAndRenderGraph(id)
})

onMounted(async () => {
  await refreshStudies()
  setupStageObserver()
})
onUnmounted(() => {
  if (pollHandle) clearInterval(pollHandle)
  if (simulation) simulation.stop()
  if (stageObserver) stageObserver.disconnect()
})
</script>

<style scoped>
.as-shell {
  max-width: 1180px;
  margin: 24px auto 80px;
  padding: 0 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  color: #1f2937;
}

/* ===== header / brand ===== */
.as-header { padding: 8px 0 18px; }
.brand { display: flex; align-items: center; gap: 12px; }
.brand-mark {
  width: 14px; height: 14px; border-radius: 4px;
  background: linear-gradient(135deg, #2c5282 0%, #4a7bb5 100%);
  display: inline-block;
}
.brand h1 { margin: 0; font-size: 28px; letter-spacing: -0.01em; }
.tagline { margin: 6px 0 14px; font-size: 14px; max-width: 760px; }

.stage-strip {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  border-top: 1px solid #e5e7eb;
  padding-top: 14px;
  font-size: 13px;
}
.stage-strip .strip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 4px 10px; border-radius: 6px;
  color: #6b7280; text-decoration: none;
  border: 1px solid transparent;
}
.stage-strip .strip:hover { color: #1f2937; background: #f8fafc; }
.stage-strip .strip.active {
  color: #1e3a5f; background: #eff6ff; border-color: #bfdbfe; font-weight: 600;
}
.stage-strip .strip-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; border-radius: 50%;
  background: #e5e7eb; color: #475569; font-size: 11px; font-weight: 700;
}
.stage-strip .strip.active .strip-num { background: #2c5282; color: #fff; }
.stage-strip .strip-sep { color: #cbd5e1; }

/* ===== stages ===== */
.stage {
  margin: 24px 0;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  scroll-margin-top: 20px;
  overflow: hidden;
}
.stage-load { border-top: 4px solid #2c5282; }
.stage-sim  { border-top: 4px solid #4a7bb5; }
.stage-res  { border-top: 4px solid #7c3aed; }

.stage-head {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 16px 22px 10px;
  border-bottom: 1px solid #f1f5f9;
  background: #fbfcfd;
}
.stage-num {
  flex-shrink: 0;
  width: 36px; height: 36px;
  border-radius: 50%;
  background: #2c5282; color: #ffffff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 17px; font-weight: 700;
}
.stage-sim  .stage-num { background: #4a7bb5; }
.stage-res  .stage-num { background: #7c3aed; }
.stage-title { margin: 0; font-size: 19px; letter-spacing: -0.005em; }
.stage-sub { margin: 2px 0 0 0; font-size: 13.5px; color: #6b7280; }

.stage-body { padding: 18px 22px 22px; }

/* ===== shared atoms ===== */
.muted { color: #6b7280; font-size: 14px; }
.muted.small, .small { font-size: 12px; }
.error { color: #b91c1c; font-size: 14px; }
.ok { color: #166534; font-size: 13px; }
.ok.small { font-size: 12px; }
.lbl {
  font-size: 11px; color: #6b7280; letter-spacing: 0.06em;
  text-transform: uppercase; font-weight: 600;
}

.row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.row .grow { flex: 1; }
.row input[type="text"], .row input[type="number"] {
  border: 1px solid #d1d5db; border-radius: 6px; padding: 6px 10px; font-size: 14px;
}
.row .narrow { width: 60px; }
.row label { font-size: 14px; }
.checkbox { display: inline-flex; align-items: center; gap: 6px; }

.file-pick {
  display: inline-flex; align-items: center; gap: 8px;
  border: 1px dashed #94a3b8; border-radius: 6px; padding: 6px 10px;
  cursor: pointer; font-size: 13px;
}
.file-pick input[type="file"] { font-size: 12px; }

.from-disk { margin-top: 4px; margin-bottom: 8px; }
.from-disk summary { font-size: 13px; color: #6b7280; cursor: pointer; }
.from-disk .row { margin-top: 8px; }

button {
  border: 1px solid #2c5282; background: #2c5282; color: #fff;
  border-radius: 6px; padding: 6px 14px; font-size: 14px; cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
button.ghost { background: transparent; color: #1f2937; border-color: #cbd5e1; }
button.ghost.primary {
  color: #2c5282; border-color: #bfdbfe; padding: 4px 10px; font-size: 12.5px;
}
button.ghost.primary:hover:not(:disabled) {
  background: #eff6ff; border-color: #93c5fd;
}
button.ghost.danger {
  color: #b91c1c; border-color: #fecaca; padding: 4px 10px; font-size: 12px;
}
button.ghost.danger:hover:not(:disabled) {
  background: #fef2f2; border-color: #fca5a5;
}

/* ===== study table ===== */
table.grid { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
table.grid th, table.grid td {
  text-align: left; padding: 7px 10px; border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}
table.grid th { background: #f8fafc; color: #475569; font-weight: 600; font-size: 12px; }
table.grid tbody tr { cursor: pointer; }
table.grid tr.selected { background: #eff6ff; }
table.grid td.action-cell { display: flex; gap: 10px; align-items: center; }
.link { color: #2c5282; font-size: 13px; text-decoration: none; }
.link:hover { text-decoration: underline; }

/* ===== universe (graph) ===== */
.universe { margin-top: 24px; }
.universe-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 6px; flex-wrap: wrap;
}
.universe-eyebrow {
  display: inline-block;
  font-size: 11px; color: #7c3aed; background: #f3e8ff;
  padding: 2px 8px; border-radius: 4px;
  letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600;
  margin-right: 10px;
  vertical-align: middle;
}
.sub-h { margin: 8px 0 8px; font-size: 16px; font-weight: 600; }

.graph-flex { display: flex; gap: 14px; align-items: stretch; flex-wrap: wrap; }
.graph-svg {
  display: block;
  background-color: #f8fafc;
  background-image: radial-gradient(circle, #cbd5e1 1px, transparent 1.2px);
  background-size: 18px 18px;
  background-position: 0 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  flex: 1 1 600px;
  height: 540px;
}
.graph-svg text { user-select: none; pointer-events: none; }
.node-panel {
  flex: 1 1 320px; max-width: 420px;
  border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 12px; background: #ffffff;
  overflow: auto; max-height: 540px;
  font-size: 13px;
}
.node-panel h4 { margin: 6px 0 8px; font-size: 15px; }
.node-panel h5 { margin: 12px 0 6px; font-size: 13px; color: #374151; }
.node-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
table.props { width: 100%; border-collapse: collapse; font-size: 12.5px; }
table.props th {
  text-align: left; vertical-align: top; padding: 4px 8px 4px 0;
  color: #6b7280; font-weight: 500; width: 35%;
}
table.props td { padding: 4px 0; }
table.props pre {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  white-space: pre-wrap; word-break: break-word;
}
.edge-list { padding-left: 0; list-style: none; margin: 4px 0 0; }
.edge-list li {
  padding: 3px 0; border-bottom: 1px dashed #f1f5f9;
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}
.edge-list .etype { font-size: 11px; color: #64748b; }

.graph-legend { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 10px; }
.legend-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 10px; border-radius: 9999px; font-size: 12px;
  background: #f3f4f6; color: #1f2937;
}
.legend-pill::before {
  content: ""; width: 9px; height: 9px; border-radius: 50%;
  display: inline-block; background: var(--lbl-color, #6b7280);
}

/* ===== stage 2 — run ===== */
.selected-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 14px; border-radius: 8px;
  background: #f0f9ff; border: 1px solid #bae6fd;
  font-size: 14px; margin-bottom: 14px;
}
.selected-bar code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
}
.run-status { margin-top: 12px; }
.run-head {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  font-size: 13.5px; margin-bottom: 8px;
}
.run-head .run-id code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.downloads { font-size: 13px; display: inline-flex; gap: 12px; margin-left: auto; }

pre.log {
  background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px;
  font-size: 12.5px; line-height: 1.4; overflow-x: auto; white-space: pre-wrap;
  max-height: 480px; overflow-y: auto; margin: 0;
}

/* ===== stage 3 — results ===== */
.placeholder {
  padding: 22px; border: 1px dashed #cbd5e1; border-radius: 8px;
  text-align: center; background: #f8fafc;
}
.headline {
  display: flex; gap: 18px; flex-wrap: wrap;
  background: #f0fdf4; padding: 12px 16px; border-radius: 8px;
  font-size: 14px; border: 1px solid #bbf7d0;
}

.report-wrap { margin-top: 18px; }
.report-html {
  background: #f8fafc; color: #1f2937;
  padding: 18px 22px; border-radius: 8px;
  border: 1px solid #e2e8f0;
  font-size: 14px; line-height: 1.65;
  max-height: 720px;
  overflow: auto;
}
.report-html :deep(h1),
.report-html :deep(h2),
.report-html :deep(h3),
.report-html :deep(h4) { margin: 16px 0 8px; line-height: 1.3; }
.report-html :deep(h1) { font-size: 20px; }
.report-html :deep(h2) { font-size: 17px; }
.report-html :deep(h3) { font-size: 15px; }
.report-html :deep(h4) { font-size: 14px; color: #475569; }
.report-html :deep(p)  { margin: 8px 0; }
.report-html :deep(ul),
.report-html :deep(ol) { margin: 6px 0 8px 22px; }
.report-html :deep(li) { margin-bottom: 3px; }
.report-html :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px; background: #eef2f7; padding: 1px 5px; border-radius: 4px;
}
.report-html :deep(strong) { color: #1f2937; }
.report-html :deep(blockquote) {
  border-left: 3px solid #cbd5e1; padding: 6px 12px;
  margin: 8px 0; background: #ffffff;
  color: #475569; font-style: italic;
}
.report-html :deep(table) {
  border-collapse: collapse; margin: 10px 0 14px;
  font-size: 13px; width: 100%;
}
.report-html :deep(thead) { background: #ffffff; }
.report-html :deep(th) {
  text-align: left; padding: 8px 10px;
  border-bottom: 1.5px solid #cbd5e1;
  font-weight: 600; color: #334155;
}
.report-html :deep(td) {
  padding: 7px 10px; border-bottom: 1px solid #e2e8f0;
  vertical-align: top;
}
.report-html :deep(tr:nth-child(even) td) { background: rgba(255,255,255,0.5); }
.report-html :deep(hr) {
  border: 0; border-top: 1px solid #e2e8f0; margin: 14px 0;
}
</style>
