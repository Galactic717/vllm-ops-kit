{{- define "ops.name" -}}
{{- .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- end -}}

{{- define "ops.selector" -}}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "ops.podSecurity" -}}
runAsNonRoot: true
runAsUser: {{ . }}
runAsGroup: {{ . }}
fsGroup: {{ . }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "ops.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "ops.secretEnv" -}}
- name: {{ .name }}
  valueFrom:
    secretKeyRef:
      name: {{ .root.Values.existingSecret }}
      key: {{ .key | default .name }}
      {{- if .optional }}
      optional: true
      {{- end }}
{{- end -}}

{{- define "ops.dbEnv" -}}
{{ include "ops.secretEnv" (dict "root" . "name" "POSTGRES_PASSWORD") }}
{{ include "ops.secretEnv" (dict "root" . "name" "REDIS_PASSWORD") }}
- name: VERSTAK_DATABASE_URL
  value: "postgresql://verstak:$(POSTGRES_PASSWORD)@{{ include "ops.name" . }}-postgres:5432/verstak"
- name: VERSTAK_REDIS_URL
  value: "redis://:$(REDIS_PASSWORD)@{{ include "ops.name" . }}-redis:6379/0"
{{- end -}}
