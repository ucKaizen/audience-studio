<template>
  <div v-if="open" class="si-overlay" @click.self="close">
    <div class="si-modal" role="dialog" aria-modal="true" :aria-label="title">
      <header class="si-head">
        <div class="si-title-block">
          <span class="si-eyebrow">Study</span>
          <h2>{{ title }}</h2>
          <p class="si-sub muted">
            <code>{{ details?.study_id }}</code>
            <span v-if="details?.nodes">
              · {{ details.nodes.length }} {{ identityLabelPlural }}
            </span>
            <span v-if="edgeCount > 0">· {{ edgeCount }} edges</span>
            <span v-if="details?.registered_at"> · registered {{ details.registered_at }}</span>
          </p>
        </div>
        <button class="si-close" aria-label="Close" @click="close">×</button>
      </header>

      <div class="si-body">
        <p v-if="loading" class="muted">Loading…</p>
        <p v-else-if="error" class="error">{{ error }}</p>

        <template v-else-if="details">
          <!-- BRIEF -->
          <section class="si-section">
            <h3>Brief</h3>
            <div class="brief-grid">
              <div><span class="lbl">Title</span><span class="val">{{ details.brief.title }}</span></div>
              <div v-if="details.brief.channel"><span class="lbl">Channel</span><span class="val">{{ details.brief.channel }}</span></div>
              <div v-if="details.brief.slot"><span class="lbl">Slot</span><span class="val">{{ details.brief.slot }}</span></div>
              <div v-if="details.brief.air_date"><span class="lbl">Air date</span><span class="val">{{ details.brief.air_date }}</span></div>
              <div v-if="details.brief.genre"><span class="lbl">Genre</span><span class="val">{{ details.brief.genre }}</span></div>
              <div v-if="details.brief.runtime_minutes"><span class="lbl">Runtime</span><span class="val">{{ details.brief.runtime_minutes }} minutes</span></div>
              <div><span class="lbl">Content id</span><span class="val"><code>{{ details.brief.content_id }}</code></span></div>
            </div>
            <p v-if="details.brief.synopsis" class="synopsis">{{ details.brief.synopsis }}</p>
            <div v-if="details.brief.rules?.length" class="rules">
              <span class="lbl">Rules</span>
              <ul>
                <li v-for="(r, i) in details.brief.rules" :key="i">{{ r }}</li>
              </ul>
            </div>
          </section>

          <!-- PANEL -->
          <section class="si-section">
            <h3>{{ identityLabelTitle }} ({{ details.nodes.length }})</h3>
            <div class="panel-table-wrap">
              <table class="panel-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th v-for="col in panelColumns" :key="col.key">{{ col.label }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="n in details.nodes" :key="n.key_value">
                    <td class="name-cell">
                      <strong>{{ n.properties.name || n.key_value }}</strong>
                      <span class="muted small">{{ n.key_value }}</span>
                    </td>
                    <td v-for="col in panelColumns" :key="col.key">
                      <span v-if="col.format === 'number'">{{ formatNumber(n.properties[col.key]) }}</span>
                      <span v-else>{{ n.properties[col.key] ?? '—' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- PROPENSITIES (collapsible) -->
          <section v-if="propensityEdgeTypes.length" class="si-section">
            <details>
              <summary><h3 class="inline">Propensities <span class="muted small">click to expand</span></h3></summary>
              <div class="prop-blocks">
                <div v-for="edgeType in propensityEdgeTypes" :key="edgeType" class="prop-block">
                  <h4>{{ humanizeEdgeType(edgeType) }}</h4>
                  <table class="prop-table">
                    <thead>
                      <tr>
                        <th>{{ identityLabelTitle }}</th>
                        <th>Top entries</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="n in details.nodes" :key="n.key_value">
                        <td>{{ n.properties.name || n.key_value }}</td>
                        <td class="prop-cell">
                          <span
                            v-for="(entry, i) in topPropsFor(n.key_value, edgeType, 5)"
                            :key="i"
                            class="prop-pill"
                          >
                            {{ entry.target_key }}
                            <span class="prop-num">{{ formatPropensity(entry.properties?.propensity) }}</span>
                          </span>
                          <span v-if="!topPropsFor(n.key_value, edgeType, 5).length" class="muted small">—</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </details>
          </section>

          <!-- VOICE / ATTRIBUTES (collapsible) -->
          <section v-if="hasAttributes" class="si-section">
            <details>
              <summary><h3 class="inline">Voice samples &amp; vocabulary <span class="muted small">click to expand</span></h3></summary>
              <div class="voice-blocks">
                <div v-for="n in details.nodes" :key="n.key_value" class="voice-block">
                  <h4>{{ n.properties.name || n.key_value }}</h4>
                  <div v-if="n.attributes?.voice_examples?.length" class="voice-list">
                    <span class="lbl small">examples</span>
                    <ul>
                      <li v-for="(ex, i) in n.attributes.voice_examples" :key="i">{{ ex }}</li>
                    </ul>
                  </div>
                  <div v-if="vocab(n).required.length" class="vocab">
                    <span class="lbl small">must use</span>
                    <span class="terms">{{ vocab(n).required.join(', ') }}</span>
                  </div>
                  <div v-if="vocab(n).forbidden.length" class="vocab">
                    <span class="lbl small">won&rsquo;t use</span>
                    <span class="terms">{{ vocab(n).forbidden.join(', ') }}</span>
                  </div>
                </div>
              </div>
            </details>
          </section>

          <!-- ENGAGEMENT CONFIG (small footer) -->
          <section v-if="details.engagement && Object.keys(details.engagement).length" class="si-section si-foot">
            <span class="lbl small">Engagement defaults</span>
            <ul class="engagement-list">
              <li v-for="(v, k) in details.engagement" :key="k">
                <code>{{ k }}</code>: <code>{{ v }}</code>
              </li>
            </ul>
          </section>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getStudyDetails } from '../api/v2'

const props = defineProps({
  open:     { type: Boolean, default: false },
  studyId:  { type: String,  default: '' }
})
const emit = defineEmits(['close'])

const details = ref(null)
const loading = ref(false)
const error   = ref('')

const title = computed(() => details.value?.name || props.studyId || 'Study')

const identityLabelTitle = computed(() => {
  const l = details.value?.identity_label || 'Identity'
  return l.charAt(0).toUpperCase() + l.slice(1)
})
const identityLabelPlural = computed(() => {
  const l = (details.value?.identity_label || 'identity').toLowerCase()
  return l.endsWith('s') ? l : l + 's'
})

const edgeCount = computed(() => {
  if (!details.value?.edges_by_type) return 0
  return Object.values(details.value.edges_by_type).reduce((a, arr) => a + arr.length, 0)
})

const propensityEdgeTypes = computed(() => {
  if (!details.value?.edges_by_type) return []
  return Object.keys(details.value.edges_by_type)
})

const hasAttributes = computed(() => {
  if (!details.value?.nodes) return false
  return details.value.nodes.some(n =>
    (n.attributes?.voice_examples?.length || 0) > 0 ||
    (n.attributes?.vocabulary_required?.length || 0) > 0 ||
    (n.attributes?.vocabulary_forbidden?.length || 0) > 0
  )
})

// Panel table columns are derived dynamically so future studies with different
// demographic columns still render — only the first ~7 non-key columns are
// shown to keep the table readable.
const panelColumns = computed(() => {
  if (!details.value?.nodes?.length) return []
  const n0 = details.value.nodes[0]
  const keyField = n0.key_field
  const HIDE = new Set([keyField, 'name'])
  const PREFERRED = ['age', 'gender', 'region', 'occupation', 'household', 'voice_register', 'rater_bias', 'clarity_sensitivity']
  const known = PREFERRED.filter(k => k in (n0.properties || {}))
  const extra = Object.keys(n0.properties || {})
    .filter(k => !HIDE.has(k) && !PREFERRED.includes(k))
    .slice(0, Math.max(0, 7 - known.length))
  const all = [...known, ...extra]
  return all.map(k => ({
    key: k,
    label: humanize(k),
    format: ['age', 'rater_bias', 'delayed_exposure_propensity', 'length_min_chars', 'length_max_chars'].includes(k) ? 'number' : 'text'
  }))
})

function humanize(s) {
  return String(s).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
function humanizeEdgeType(t) {
  // PROPENSITY_FOR_GENRE -> Genre propensity
  const m = /^PROPENSITY_FOR_(.+)$/.exec(t)
  if (m) return humanize(m[1].toLowerCase()) + ' propensity'
  return humanize(t.toLowerCase())
}
function formatNumber(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isFinite(n)) return Number.isInteger(n) ? String(n) : n.toFixed(2)
  return String(v)
}
function formatPropensity(v) {
  if (v === null || v === undefined || v === '') return ''
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : String(v)
}
function topPropsFor(sourceKey, edgeType, limit) {
  const all = details.value?.edges_by_type?.[edgeType] || []
  return all
    .filter(e => e.source_key === sourceKey)
    .sort((a, b) => (b.properties?.propensity || 0) - (a.properties?.propensity || 0))
    .slice(0, limit)
}
function vocab(n) {
  return {
    required:  n.attributes?.vocabulary_required  || [],
    forbidden: n.attributes?.vocabulary_forbidden || []
  }
}

function close() { emit('close') }

watch(() => [props.open, props.studyId], async ([open, sid]) => {
  if (!open || !sid) return
  details.value = null
  error.value = ''
  loading.value = true
  try {
    const res = await getStudyDetails(sid)
    details.value = res.data
  } catch (err) {
    error.value = String(err?.response?.data?.error || err?.message || err)
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>

<style scoped>
.si-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  padding: 24px;
}
.si-modal {
  background: #ffffff;
  width: min(1100px, 100%);
  max-height: 92vh;
  border-radius: 12px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.25);
  display: flex; flex-direction: column;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  color: #1f2937;
}
.si-head {
  padding: 18px 24px 14px;
  border-bottom: 1px solid #e5e7eb;
  display: flex; align-items: flex-start; gap: 16px;
}
.si-title-block { flex: 1; min-width: 0; }
.si-eyebrow {
  font-size: 11px; color: #2c5282; letter-spacing: 0.08em;
  text-transform: uppercase; font-weight: 600;
}
.si-head h2 { margin: 4px 0 2px; font-size: 20px; }
.si-sub { margin: 0; font-size: 13px; }
.si-sub code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }
.si-close {
  border: 1px solid #cbd5e1; background: transparent; color: #475569;
  width: 36px; height: 36px; border-radius: 8px;
  font-size: 22px; line-height: 1; cursor: pointer;
}
.si-close:hover { background: #f1f5f9; color: #1f2937; }

.si-body { padding: 16px 24px 24px; overflow-y: auto; }

.si-section { margin-top: 16px; }
.si-section h3 { margin: 0 0 10px 0; font-size: 16px; font-weight: 600; }
.si-section h3.inline { display: inline; }
.si-section h4 { margin: 0 0 8px 0; font-size: 13.5px; font-weight: 600; color: #334155; }
.si-section details > summary { cursor: pointer; list-style: revert; padding: 4px 0; }
.si-section details > summary::-webkit-details-marker { color: #94a3b8; }
.si-section details[open] > summary { margin-bottom: 10px; }

/* Brief */
.brief-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 24px;
  margin-bottom: 12px;
}
.brief-grid > div { display: flex; flex-direction: column; gap: 2px; }
.brief-grid .lbl {
  font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em;
}
.brief-grid .val { font-size: 14px; }
.synopsis {
  font-size: 14px; line-height: 1.55;
  border-left: 3px solid #cbd5e1;
  padding: 8px 14px; margin: 8px 0 12px;
  background: #f8fafc; border-radius: 0 6px 6px 0;
  white-space: pre-wrap;
}
.rules .lbl {
  font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em;
}
.rules ul { margin: 4px 0 0; padding-left: 20px; font-size: 13.5px; }
.rules li { margin-bottom: 3px; }

/* Panel table */
.panel-table-wrap { overflow-x: auto; }
.panel-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.panel-table th {
  text-align: left; padding: 8px 10px; border-bottom: 1.5px solid #cbd5e1;
  font-weight: 600; color: #334155; background: #f8fafc;
  position: sticky; top: 0;
}
.panel-table td {
  padding: 8px 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top;
}
.panel-table tr:last-child td { border-bottom: none; }
.panel-table .name-cell { display: flex; flex-direction: column; gap: 2px; }

/* Propensity table */
.prop-blocks { display: flex; flex-direction: column; gap: 14px; }
.prop-block { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 14px; background: #ffffff; }
.prop-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.prop-table th {
  text-align: left; padding: 6px 10px; border-bottom: 1px solid #e5e7eb;
  font-weight: 600; color: #475569; font-size: 12px;
}
.prop-table td { padding: 6px 10px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.prop-cell { display: flex; flex-wrap: wrap; gap: 6px; }
.prop-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 9px; border-radius: 9999px;
  background: #eff6ff; color: #1e40af;
  font-size: 12px;
}
.prop-num { color: #475569; font-variant-numeric: tabular-nums; font-size: 11.5px; }

/* Voice */
.voice-blocks { display: flex; flex-direction: column; gap: 14px; }
.voice-block { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 14px; background: #ffffff; }
.voice-list ul { margin: 4px 0 0; padding-left: 20px; font-size: 13px; }
.voice-list li { margin-bottom: 3px; }
.vocab { margin-top: 6px; font-size: 13px; }
.vocab .lbl { display: inline-block; min-width: 80px; color: #6b7280; }
.vocab .terms { color: #334155; }
.lbl.small { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280; }

/* Footer */
.si-foot { padding-top: 12px; border-top: 1px solid #f1f5f9; }
.engagement-list { list-style: none; padding: 0; margin: 4px 0 0; display: flex; gap: 16px; flex-wrap: wrap; font-size: 12.5px; }
.engagement-list code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

.muted { color: #6b7280; }
.muted.small, .small { font-size: 12px; }
.error { color: #b91c1c; font-size: 14px; }
</style>
