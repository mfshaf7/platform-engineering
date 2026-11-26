"""Render the restricted, dedicated project namespace from reviewed recipe inputs."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re

from console_project_runtime_setup import NODE_SCRIPTS, PAIRED_NODE_RECIPE, source_path


IMAGE = re.compile(r"[a-zA-Z0-9._:/-]+@sha256:[a-f0-9]{64}")
SCOPE = re.compile(r"sha256:([a-f0-9]{64})")
OPERATION = re.compile(r"project-operation:([a-f0-9]{64})")
DENY = {"policyTypes": ["Ingress", "Egress"], "podSelector": {}, "ingress": [], "egress": []}


def binary_quantity(mib: int) -> str:
    value = mib
    units = ("Mi", "Gi", "Ti", "Pi", "Ei")
    for index, unit in enumerate(units):
        if value % 1024 or index == len(units) - 1:
            return f"{value}{unit}"
        value //= 1024
    raise AssertionError("A Kubernetes binary quantity unit is required.")


@dataclass(frozen=True)
class WorkloadLimits:
    cpu_millis: int
    memory_mib: int
    temporary_mib: int
    deadline_seconds: int

    def __post_init__(self):
        if not all(type(value) is int and value > 0 for value in (self.cpu_millis, self.memory_mib,
                                                                 self.temporary_mib, self.deadline_seconds)):
            raise ValueError("Positive reviewed workload limits are required.")

    def quantities(self):
        whole, remainder = divmod(self.cpu_millis, 1000)
        return {"cpu": f"{self.cpu_millis}m" if remainder else str(whole), "memory": binary_quantity(self.memory_mib),
                "ephemeral-storage": binary_quantity(self.temporary_mib)}


@dataclass(frozen=True)
class SandboxRecipe:
    image: str
    transfer_image: str
    build: WorkloadLimits
    serve: WorkloadLimits
    aggregate: WorkloadLimits
    storage_mib: int
    output_mib: int
    run_port: int = 3000

    def __post_init__(self):
        if (not all(isinstance(value, str) and IMAGE.fullmatch(value) for value in (self.image, self.transfer_image))
                or not all(type(value) is int and value > 0 for value in (self.storage_mib, self.output_mib))
                or self.storage_mib <= self.output_mib
                or type(self.run_port) is not int or not 1024 <= self.run_port <= 65535):
            raise ValueError("Pinned images and reviewed sandbox storage and network limits are required.")
        for metric in ("cpu_millis", "memory_mib", "temporary_mib"):
            if getattr(self.aggregate, metric) < getattr(self.build, metric) + getattr(self.serve, metric):
                raise ValueError("The installation sandbox limit must cover the build and one serving workload.")


class ProjectSandbox:
    """Names and all pod commands are owner derived. Project source enters by PVC."""

    def __init__(self, scope_digest: str, operation_id: str, recipe: SandboxRecipe):
        scope = SCOPE.fullmatch(scope_digest)
        operation = OPERATION.fullmatch(operation_id)
        if scope is None or operation is None:
            raise ValueError("A retained project command and scope are required.")
        self.namespace = f"devint-project-{scope[1][:32]}"
        self.generation = operation[1][:32]
        self.scope = scope_digest
        self.operation = operation_id
        self.recipe = recipe

    def _metadata(self, name: str, *, namespace: bool = True):
        value = {"name": name, "labels": {"app.kubernetes.io/managed-by": "platform-project-runtime"},
                 "annotations": {"platform.project/scope": self.scope}}
        if namespace:
            value["namespace"] = self.namespace
        return value

    def policy(self):
        namespace = self._metadata(self.namespace, namespace=False)
        namespace["labels"].update({"pod-security.kubernetes.io/enforce": "restricted",
                                    "pod-security.kubernetes.io/audit": "restricted",
                                    "pod-security.kubernetes.io/warn": "restricted"})
        limits = {f"limits.{key}": value for key, value in self.recipe.aggregate.quantities().items()}
        requests = {f"requests.{key}": value for key, value in self.recipe.aggregate.quantities().items()}
        quota = {**limits, **requests, "pods": "4", "requests.storage": binary_quantity(self.recipe.storage_mib),
                 "persistentvolumeclaims": "8"}
        return [
            {"apiVersion": "v1", "kind": "Namespace", "metadata": namespace},
            {"apiVersion": "v1", "kind": "ResourceQuota", "metadata": self._metadata("project-budget"),
             "spec": {"hard": quota}},
            {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": self._metadata("project-deny"),
             "spec": {"policyTypes": list(DENY["policyTypes"]), "podSelector": {}, "ingress": [], "egress": []}},
        ]

    def same_project_api_policy(self, port: int):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("The declared same-project API must use an admitted unprivileged port.")
        generation = {"platform.project/generation": self.generation}
        frontend = {"matchLabels": {"platform.project/role": "frontend", **generation}}
        api = {"matchLabels": {"platform.project/role": "api", **generation}}
        ports = [{"protocol": "TCP", "port": port}]
        ingress = self._metadata(f"project-api-ingress-{self.generation}")
        egress = self._metadata(f"project-frontend-egress-{self.generation}")
        for metadata in (ingress, egress):
            metadata["annotations"]["platform.project/operation"] = self.operation
        return [
            {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": ingress,
             "spec": {"podSelector": api, "policyTypes": ["Ingress"],
                      "ingress": [{"from": [{"podSelector": frontend}], "ports": ports}]}},
            {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": egress,
             "spec": {"podSelector": frontend, "policyTypes": ["Egress"],
                      "egress": [{"to": [{"podSelector": api}], "ports": ports}]}},
        ]

    def volume_name(self, role: str):
        if role not in ("input", "build", "dependencies", "data"):
            raise ValueError("Unknown project volume role.")
        return f"{role}-{self.generation}"

    def volume(self, role: str, storage_mib: int):
        if type(storage_mib) is not int or not 0 < storage_mib <= self.recipe.storage_mib:
            raise ValueError("Project storage must fit its reviewed budget.")
        metadata = self._metadata(self.volume_name(role))
        metadata["annotations"]["platform.project/operation"] = self.operation
        return {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": metadata,
                "spec": {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": binary_quantity(storage_mib)}}}}

    def _pod(self, role, *, image, command, mounts, limits, maximum_age=None, environment=None, port=None,
             termination_grace=None):
        metadata = self._metadata(f"{role}-{self.generation}")
        metadata["annotations"]["platform.project/operation"] = self.operation
        metadata["labels"].update({"platform.project/role": role, "platform.project/generation": self.generation})
        volumes = [{"name": role, "persistentVolumeClaim": {"claimName": self.volume_name(role), "readOnly": readonly}}
                   for role, _, readonly in mounts]
        volumes.append({"name": "temporary", "emptyDir": {"sizeLimit": binary_quantity(limits.temporary_mib)}})
        mountpoints = [{"name": role, "mountPath": path, "readOnly": readonly} for role, path, readonly in mounts]
        mountpoints.append({"name": "temporary", "mountPath": "/tmp"})
        quantity = limits.quantities()
        container = {"name": "project", "image": image, "imagePullPolicy": "IfNotPresent", "command": command,
                     "env": [{"name": key, "value": value} for key, value in (environment or {}).items()],
                     "resources": {"requests": quantity, "limits": dict(quantity)}, "volumeMounts": mountpoints,
                     "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                         "capabilities": {"drop": ["ALL"]}}}
        if port is not None:
            container["ports"] = [{"name": "project-http", "containerPort": port}]
            container["readinessProbe"] = {"httpGet": {"path": "/", "port": port}, "failureThreshold": 3,
                                           "timeoutSeconds": 1, "periodSeconds": 3}
        spec = {"automountServiceAccountToken": False, "enableServiceLinks": False, "restartPolicy": "Never",
                "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000, "fsGroup": 1000,
                                    "seccompProfile": {"type": "RuntimeDefault"}}, "volumes": volumes, "containers": [container]}
        if maximum_age is not None:
            spec["activeDeadlineSeconds"] = maximum_age
        if termination_grace is not None:
            spec["terminationGracePeriodSeconds"] = termination_grace
        return {"apiVersion": "v1", "kind": "Pod", "metadata": metadata, "spec": spec}

    def transfer_pod(self):
        # The fixed image receives bytes only through the owner-controlled transfer.
        # It has no executor socket, API token, registry credential or network route.
        limits = self.recipe.build
        return self._pod("transfer", image=self.recipe.transfer_image, command=["/bin/sleep", str(limits.deadline_seconds)],
                         mounts=[("input", "/project-input", False), ("dependencies", "/approved-cache", False)],
                         limits=limits, maximum_age=limits.deadline_seconds, termination_grace=1)

    def artifact_reader(self):
        limits = self.recipe.build
        return self._pod("artifact-reader", image=self.recipe.transfer_image,
                         command=["/bin/sleep", str(limits.deadline_seconds)],
                         mounts=[("build", "/project-build", True)], limits=limits,
                         maximum_age=limits.deadline_seconds, termination_grace=1)

    def copy_retained_data(self, previous_claim):
        if not isinstance(previous_claim, str) or not re.fullmatch(r"data-[a-f0-9]{32}", previous_claim):
            raise ValueError("Copying retained data requires a verified project data volume.")
        limits = self.recipe.build
        copy = ('shopt -s dotglob nullglob; entries=(/previous-data/*); '
                'if (( ${#entries[@]} )); then cp -a --no-preserve=ownership -- "${entries[@]}" /project-data/; fi')
        document = self._pod("data-copy", image=self.recipe.transfer_image,
                             command=["/bin/bash", "-ec", copy],
                             mounts=[("data", "/project-data", False)], limits=limits, maximum_age=limits.deadline_seconds)
        spec = document["spec"]
        spec["volumes"].append({"name": "previous", "persistentVolumeClaim": {"claimName": previous_claim, "readOnly": True}})
        spec["containers"][0]["volumeMounts"].append({"name": "previous", "mountPath": "/previous-data", "readOnly": True})
        return document

    def build_pod(self, recipe_id: str, app_root: str):
        if recipe_id != "static" and recipe_id not in NODE_SCRIPTS:
            raise ValueError("The selected recipe does not have a build workload.")
        app = "." if app_root == "." else source_path(app_root)
        cwd = f"/tmp/work/{app}"
        if recipe_id == "static":
            command = ["/bin/bash", "-ec", 'cp -R -- "$1/." /project-build/', "copy-static", f"/project-input/{app}"]
        else:
            shell = ('mkdir -p /tmp/work /tmp/npm-cache; cp -R -- /project-input/. /tmp/work/; '
                     'cp -R -- /approved-cache/. /tmp/npm-cache/; cd -- "$1"; '
                     'npm ci --offline --ignore-scripts --no-audit --no-fund --cache /tmp/npm-cache; ')
            if recipe_id == "node-frontend":
                shell += 'npm run build; test -d dist; cp -R -- dist/. /project-build/'
            else:
                if recipe_id == PAIRED_NODE_RECIPE:
                    shell += 'npm run build; '
                shell += 'cp -R -- . /project-build/'
            command = ["/bin/bash", "-ec", shell, "build-project", cwd]
        limits = self.recipe.build
        return self._pod("build", image=self.recipe.image, command=command, limits=limits,
                         mounts=[("input", "/project-input", True), ("dependencies", "/approved-cache", True),
                                 ("build", "/project-build", False)], maximum_age=limits.deadline_seconds,
                         environment={"HOME": "/tmp", "NPM_CONFIG_USERCONFIG": "/dev/null", "GIT_TERMINAL_PROMPT": "0"})

    def runtime_pod(self, recipe_id: str, *, artifact_claim: str, data_claim: str | None = None,
                    api_address: str | None = None, api_port: int | None = None):
        if not re.fullmatch(r"build-[a-f0-9]{32}", artifact_claim):
            raise ValueError("The running artifact must be an exact owner-qualified build volume.")
        if recipe_id != "static" and recipe_id not in NODE_SCRIPTS:
            raise ValueError("The selected recipe does not run a workload.")
        if recipe_id == PAIRED_NODE_RECIPE and api_address is None:
            raise ValueError("The paired frontend requires its own verified API endpoint.")
        port = self.recipe.run_port
        role = "api" if recipe_id == "node-api" else "frontend"
        environment = {"HOME": "/tmp", "PORT": str(port), "HOST": "0.0.0.0", "NODE_ENV": "production"}
        if api_address is not None:
            address = ipaddress.ip_address(api_address)
            if role != "frontend" or type(api_port) is not int or not 1024 <= api_port <= 65535:
                raise ValueError("Only an admitted frontend may receive its same-project API address.")
            host = f"[{address}]" if address.version == 6 else str(address)
            environment["PROJECT_API_ORIGIN"] = f"http://{host}:{api_port}"
        mounts = [("build", "/project-build", True)]
        if data_claim is not None:
            if not isinstance(data_claim, str) or not re.fullmatch(r"data-[a-f0-9]{32}", data_claim):
                raise ValueError("Declared project data requires an exact owner volume.")
            mounts.append(("data", "/project-data", False))
        if recipe_id == PAIRED_NODE_RECIPE:
            command = ["npm", "--prefix", "/project-build", "run", "start:frontend"]
        elif role == "api":
            command = ["npm", "--prefix", "/project-build", "start"]
        else:
            command = ["node", "-e", STATIC_SERVER]
        result = self._pod(role, image=self.recipe.image, command=command, mounts=mounts, limits=self.recipe.serve,
                           environment=environment, port=port)
        build = next(item for item in result["spec"]["volumes"] if item["name"] == "build")
        build["persistentVolumeClaim"]["claimName"] = artifact_claim
        if data_claim is not None:
            data = next(item for item in result["spec"]["volumes"] if item["name"] == "data")
            data["persistentVolumeClaim"]["claimName"] = data_claim
        return result


STATIC_SERVER = r'''
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = '/project-build';
const types = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.webp':'image/webp','.woff2':'font/woff2'};
http.createServer((req,res) => {
  try {
    if (!['GET','HEAD'].includes(req.method)) { res.writeHead(405).end(); return; }
    const requested = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const relative = requested.endsWith('/') ? `${requested}index.html` : requested;
    if (relative.split('/').some(part => part.startsWith('.'))) { res.writeHead(404).end(); return; }
    const file = fs.realpathSync(path.resolve(root, `.${relative}`));
    if (!file.startsWith(`${root}/`) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
    res.writeHead(200, {'content-type':types[path.extname(file)] || 'application/octet-stream', 'x-content-type-options':'nosniff'});
    if (req.method === 'HEAD') { res.end(); return; }
    fs.createReadStream(file).on('error', () => res.destroy()).pipe(res);
  } catch { res.writeHead(404).end(); }
}).listen(Number(process.env.PORT),'0.0.0.0');
'''
