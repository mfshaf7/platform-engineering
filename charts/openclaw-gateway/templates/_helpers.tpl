{{- define "openclaw-gateway.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "openclaw-gateway.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- include "openclaw-gateway.name" . -}}
{{- end -}}
{{- end -}}


{{- define "openclaw-gateway.imageRef" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag -}}
{{- end -}}
{{- end -}}

{{- define "openclaw-gateway.imageIdentity" -}}
{{- if .Values.image.digest -}}
{{- trimPrefix "sha256:" .Values.image.digest | trunc 12 -}}
{{- else -}}
{{- .Values.image.tag | lower | replace "." "-" | replace ":" "-" | replace "_" "-" | trunc 12 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "openclaw-gateway.prepullJobName" -}}
{{- printf "%s-prepull-%s" (include "openclaw-gateway.fullname" .) (include "openclaw-gateway.imageIdentity" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
