HTML_CONTROL = """<!DOCTYPE html>
<html>
<head>
    <title>V4L2 Camera Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: sans-serif; margin: 0; padding: 1em; background-color: #f0f0f0; }
        .container { max-width: 800px; margin: 0 auto; background-color: #fff; padding: 1em; border-radius: 5px; }
        h1, h2 { color: #333; }
        .selectors { display: flex; gap: 1em; margin-bottom: 1em; flex-wrap: wrap; }
        .selectors label { font-weight: bold; }
        select { padding: 0.5em; border-radius: 3px; border: 1px solid #ccc; }
        .preview { margin-bottom: 1em; }
        .preview-container { border: 1px solid #ccc; min-height: 240px; display: flex; justify-content: center; align-items: center; background-color: #000; }
        .preview-container img, .preview-container iframe { max-width: 100%; height: auto; }
        .controls-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1em; }
        .control { margin-bottom: 1em; }
        .control label { display: block; font-weight: bold; margin-bottom: 0.25em; }
        .control input[type=range] { width: 100%; }
        .control input[type=checkbox] { transform: scale(1.2); }
        .control select { width: 100%; }
        .status { margin-top: 1em; background-color: #eee; padding: 1em; border-radius: 3px; }
        .status pre { white-space: pre-wrap; word-wrap: break-word; font-size: 0.9em; }
        .warning { background-color: #fff3cd; color: #856404; padding: 1em; border: 1px solid #ffeeba; border-radius: 3px; margin-top: 1em; }
        button { padding: 0.75em 1.5em; border: none; background-color: #007bff; color: #fff; border-radius: 3px; cursor: pointer; font-size: 1em; }
        button:hover { background-color: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>V4L2 Camera Control</h1>

        <div class="selectors">
            <div>
                <label for="cam-select">Camera:</label>
                <select id="cam-select">
                    <option value="1">Cam 1</option>
                    <option value="2">Cam 2</option>
                </select>
            </div>
            <div>
                <label for="mode-select">Mode:</label>
                <select id="mode-select">
                    <option value="webrtc">WebRTC</option>
                    <option value="mjpg">MJPG</option>
                    <option value="snapshot">Snapshot</option>
                </select>
            </div>
        </div>

        <div class="preview">
            <h2>Preview</h2>
            <div class="preview-container" id="preview-container">
                <!-- Stream will be embedded here -->
            </div>
        </div>

        <div class="controls">
            <h2>Controls</h2>
            <div id="controls-container" class="controls-container">
                <!-- Controls will be dynamically inserted here -->
            </div>
            <button id="apply-btn">Apply Changes</button>
        </div>

        <div class="status">
            <h2>Status</h2>
            <pre id="status-output">Loading device info...</pre>
        </div>

        <div class="warning">
            <strong>Note:</strong> Changes are not persisted. Restart the service to reset to default values.
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const elements = {
                camSelect: document.getElementById('cam-select'),
                modeSelect: document.getElementById('mode-select'),
                previewContainer: document.getElementById('preview-container'),
                controlsContainer: document.getElementById('controls-container'),
                applyBtn: document.getElementById('apply-btn'),
                statusOutput: document.getElementById('status-output')
            };

            const streamUrlBase = '%%STREAM_URL_BASE%%';

            function getBasePath() {
                const camId = elements.camSelect.value;
                const base = streamUrlBase || '';
                return camId === '2' ? `${base}/webcam2` : `${base}/webcam`;
            }

            function updatePreview() {
                const mode = elements.modeSelect.value;
                const basePath = getBasePath();
                let content = '';

                if (!streamUrlBase) {
                    elements.previewContainer.innerHTML = '<p style="color: red;">Stream URL base not configured.</p>';
                    return;
                }

                switch (mode) {
                    case 'webrtc':
                        content = `<iframe src="${basePath}/webrtc"></iframe>`;
                        break;
                    case 'mjpg':
                        content = `<img src="${basePath}/stream.mjpg" />`;
                        break;
                    case 'snapshot':
                        content = `<img id="snapshot-img" src="${basePath}/snapshot.jpg" />`;
                        break;
                }
                elements.previewContainer.innerHTML = content;
            }

            async function fetchControls() {
                const camId = elements.camSelect.value;
                try {
                    const response = await fetch(`/api/v4l2/ctrls?cam=${camId}`);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const controls = await response.json();
                    renderControls(controls);
                } catch (error) {
                    elements.controlsContainer.innerHTML = `<p style="color: red;">Error fetching controls: ${error.message}</p>`;
                }
            }

            function renderControls(controls) {
                elements.controlsContainer.innerHTML = '';
                controls.forEach(ctrl => {
                    const controlEl = document.createElement('div');
                    controlEl.classList.add('control');

                    let inputHtml = '';
                    const label = `<label for="ctrl-${ctrl.name}">${ctrl.name.replace(/_/g, ' ')}</label>`;

                    switch (ctrl.type) {
                        case 'integer':
                            inputHtml = `
                                ${label}
                                <input type="range" id="ctrl-${ctrl.name}" name="${ctrl.name}" min="${ctrl.min}" max="${ctrl.max}" step="${ctrl.step}" value="${ctrl.value}">
                                <span class="value-display">${ctrl.value}</span>`;
                            break;
                        case 'boolean':
                            inputHtml = `
                                ${label}
                                <input type="checkbox" id="ctrl-${ctrl.name}" name="${ctrl.name}" ${ctrl.value ? 'checked' : ''}>`;
                            break;
                        case 'menu':
                            const options = ctrl.menu.map(item =>
                                `<option value="${item.value}" ${item.value === ctrl.value ? 'selected' : ''}>${item.label}</option>`
                            ).join('');
                            inputHtml = `
                                ${label}
                                <select id="ctrl-${ctrl.name}" name="${ctrl.name}">${options}</select>`;
                            break;
                        default:
                             inputHtml = `${label}<span>Unsupported control type: ${ctrl.type}</span>`;
                    }
                    controlEl.innerHTML = inputHtml;
                    elements.controlsContainer.appendChild(controlEl);
                });

                 // Add event listener for range inputs to update the display
                elements.controlsContainer.querySelectorAll('input[type=range]').forEach(input => {
                    input.addEventListener('input', (e) => {
                        e.target.nextElementSibling.textContent = e.target.value;
                    });
                });
            }

            async function fetchInfo() {
                const camId = elements.camSelect.value;
                try {
                    const response = await fetch(`/api/v4l2/info?cam=${camId}`);
                     if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const data = await response.json();
                    elements.statusOutput.textContent = data.info;
                } catch (error) {
                    elements.statusOutput.textContent = `Error fetching device info: ${error.message}`;
                }
            }

            async function applyChanges() {
                const camId = elements.camSelect.value;
                const settings = {};
                const inputs = elements.controlsContainer.querySelectorAll('input, select');
                inputs.forEach(input => {
                    const name = input.name;
                    let value;
                    if (input.type === 'checkbox') {
                        value = input.checked ? 1 : 0;
                    } else {
                        value = parseInt(input.value, 10);
                    }
                    settings[name] = value;
                });

                try {
                    const response = await fetch(`/api/v4l2/set?cam=${camId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(settings)
                    });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.error || `HTTP error! status: ${response.status}`);
                    }

                    // Refresh snapshot for visual feedback
                    const snapshotImg = document.getElementById('snapshot-img');
                    if (snapshotImg) {
                        snapshotImg.src = `${getBasePath()}/snapshot.jpg?t=${new Date().getTime()}`;
                    }

                    // Optionally, refresh all controls to reflect current state
                    fetchControls();

                } catch (error) {
                    alert(`Error applying changes: ${error.message}`);
                }
            }

            elements.camSelect.addEventListener('change', () => {
                const camId = elements.camSelect.value;
                const url = new URL(window.location);
                url.searchParams.set('cam', camId);
                window.history.pushState({}, '', url);

                updatePreview();
                fetchControls();
                fetchInfo();
            });

            elements.modeSelect.addEventListener('change', updatePreview);
            elements.applyBtn.addEventListener('click', applyChanges);

            function initializeApp() {
                // You might want to set the initial cam based on URL or a default
                const urlParams = new URLSearchParams(window.location.search);
                const cam = urlParams.get('cam');
                if (cam) {
                    elements.camSelect.value = cam;
                }

                updatePreview();
                fetchControls();
                fetchInfo();
            }

            initializeApp();
        });
    </script>
</body>
</html>
"""
