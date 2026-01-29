(function() {
    console.log('[Cytoscape] Starting initialization...');
    var attempts = 0;
    var maxAttempts = 300; // 30 seconds worth of attempts
    
    // Wait for both the cy element and cytoscape library to be available
    function initWhenReady() {
        attempts++;
        
        if (attempts > maxAttempts) {
            console.error('[Cytoscape] Initialization timed out after 30 seconds');
            return;
        }
        
        var cyElement = document.getElementById('cy');
        if (!cyElement) {
            if (attempts % 10 === 0) {
                console.log('[Cytoscape] Still waiting for #cy element... (attempt ' + attempts + ')');
            }
            setTimeout(initWhenReady, 100);
            return;
        }
        
        if (typeof cytoscape === 'undefined') {
            if (attempts % 10 === 0) {
                console.log('[Cytoscape] Still waiting for cytoscape library... (attempt ' + attempts + ')');
            }
            setTimeout(initWhenReady, 100);
            return;
        }
        
        console.log('[Cytoscape] Found #cy element and cytoscape library after ' + attempts + ' attempts');
        console.log('[Cytoscape] Element dimensions:', cyElement.offsetWidth, 'x', cyElement.offsetHeight);
        
        // Check if there's an existing instance and destroy it properly
        if (window.cy && typeof window.cy.destroy === 'function') {
            console.log('[Cytoscape] Destroying existing instance');
            try {
                window.cy.destroy();
            } catch (e) {
                console.warn('[Cytoscape] Error destroying existing instance:', e);
            }
        }
        
        // Initialize Cytoscape immediately
        try {
            console.log('[Cytoscape] Creating new instance...');
            console.log('[Cytoscape] Using initial topology:', window.initialTopology ? 'Found' : 'Missing');
            
            var cy = window.cy = cytoscape({
                container: document.getElementById('cy'),
                elements: window.initialTopology || [],
                style: [
                    {
                        selector: 'node',
                        style: {
                            'label': 'data(label)',
                            'text-valign': 'bottom',
                            'text-halign': 'center',
                            'text-margin-y': 5,
                            'font-size': '12px',
                            'font-weight': 'bold',
                            'color': '#f1f5f9',
                            'text-outline-color': '#0f172a',
                            'text-outline-width': 2,
                            'width': 50,
                            'height': 50,
                            'background-fit': 'contain',
                            'background-clip': 'none'
                        }
                    },
                    {
                        selector: 'node.switch',
                        style: {
                            'background-opacity': 0,
                            'background-image': 'data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22%237c3aed%22%3E%3Cpath%20d%3D%22M2%2C6%20L22%2C6%20L22%2C18%20L2%2C18%20L2%2C6%20Z%20M4%2C8%20L4%2C16%20L20%2C16%20L20%2C8%20L4%2C8%20Z%20M6%2C10%20L8%2C10%20L8%2C14%20L6%2C14%20L6%2C10%20Z%20M10%2C10%20L12%2C10%20L12%2C14%20L10%2C14%20L10%2C10%20Z%20M14%2C10%20L16%2C10%20L16%2C14%20L14%2C14%20L14%2C10%20Z%20M18%2C10%20L20%2C10%20L20%2C14%20L18%2C14%20L18%2C10%20Z%22%2F%3E%3C%2Fsvg%3E',
                            'shape': 'rectangle'
                        }
                    },
                    {
                        selector: 'node.hca',
                        style: {
                            'background-opacity': 0,
                            'background-image': 'data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22%230891b2%22%3E%3Cpath%20d%3D%22M4%2C2%20L20%2C2%20C21.1%2C2%2022%2C2.9%2022%2C4%20L22%2C20%20C22%2C21.1%2021.1%2C22%2020%2C22%20L4%2C22%20C2.9%2C22%202%2C21.1%202%2C20%20L2%2C4%20C2%2C2.9%202.9%2C2%204%2C2%20Z%20M6%2C6%20L18%2C6%20L18%2C10%20L6%2C10%20L6%2C6%20Z%20M6%2C12%20L18%2C12%20L18%2C16%20L6%2C16%20L6%2C12%20Z%22%2F%3E%3C%2Fsvg%3E',
                            'shape': 'rectangle'
                        }
                    },
                    {
                        selector: 'node:selected',
                        style: {
                            'border-color': '#00d9ff',
                            'border-width': 2,
                            'border-opacity': 1,
                            'background-opacity': 0.1,
                            'background-color': '#ffffff'
                        }
                    },
                    {
                        selector: 'edge',
                        style: {
                            'width': 2,
                            'line-color': '#64748b',
                            'curve-style': 'bezier',
                            'control-point-step-size': 40,
                            'label': 'data(label)',
                            'font-size': '9px',
                            'color': '#94a3b8',
                            'text-background-color': '#0f172a',
                            'text-background-opacity': 0.9,
                            'text-background-padding': '2px',
                            'text-rotation': 'autorotate'
                        }
                    },
                    {
                        selector: 'edge:selected',
                        style: {
                            'line-color': '#00d9ff',
                            'target-arrow-color': '#00d9ff',
                            'width': 3,
                            'label': 'data(label)'
                        }
                    }
                ],
                layout: {
                    name: 'breadthfirst',
                    directed: true,
                    padding: 50,
                    spacingFactor: 1.75,
                    avoidOverlap: true,
                    nodeDimensionsIncludeLabels: true,
                    // Start from spine switches
                    roots: function(ele) {
                        var label = ele.data('label').toLowerCase();
                        return label.includes('spine');
                    },
                    // Custom depth sorting: spines -> leafs -> HCAs
                    depthSort: function(a, b) {
                        var aLabel = a.data('label').toLowerCase();
                        var bLabel = b.data('label').toLowerCase();
                        
                        // Determine layer rank
                        var aRank = aLabel.includes('spine') ? 1 : (aLabel.includes('leaf') ? 2 : 3);
                        var bRank = bLabel.includes('spine') ? 1 : (bLabel.includes('leaf') ? 2 : 3);
                        
                        if (aRank !== bRank) {
                            return aRank - bRank;
                        }
                        // Within same rank, sort alphabetically
                        return aLabel.localeCompare(bLabel);
                    }
                }
            });
            
            // Manual connection mode state
            var connectionMode = {
                active: false,
                sourceNode: null
            };
            
            console.log('[Cytoscape] Basic editor initialized (no extensions)');
            
            // Store global state
            window.cyState = {
                mode: 'select',  // 'select', 'add_switch', 'add_hca', 'connect'
                selectedElement: null,
                nodeCounter: { Switch: 0, Hca: 0 }
            };
            
            // Helper function to dispatch custom events for property panel updates
            function showNodeProperties(node) {
                var detail = {
                    id: node.id(),
                    label: node.data('label'),
                    type: node.data('type'),
                    ports: node.data('ports')
                };
                console.log('[Cytoscape] Dispatching cy-node-selected event with detail:', detail);
                
                var event = new CustomEvent('cy-node-selected', {
                    detail: detail,
                    bubbles: true,
                    cancelable: true
                });
                
                window.dispatchEvent(event);
                console.log('[Cytoscape] Event dispatched successfully');
            }
            
            function showEdgeProperties(edge) {
                var detail = {
                    id: edge.id(),
                    source: edge.source().id(),
                    target: edge.target().id(),
                    sourcePort: edge.data('sourcePort'),
                    targetPort: edge.data('targetPort')
                };
                console.log('[Cytoscape] Dispatching cy-edge-selected event with detail:', detail);
                
                var event = new CustomEvent('cy-edge-selected', {
                    detail: detail,
                    bubbles: true,
                    cancelable: true
                });
                
                window.dispatchEvent(event);
                console.log('[Cytoscape] Event dispatched successfully');
            }
            
            function showEmptyProperties() {
                console.log('[Cytoscape] Dispatching cy-deselect event');
                var event = new CustomEvent('cy-deselect', {
                    bubbles: true,
                    cancelable: true
                });
                window.dispatchEvent(event);
            }
            
            // Validation helper: Check if port is already in use
            function isPortInUse(node, portNum) {
                var edges = node.connectedEdges();
                for (var i = 0; i < edges.length; i++) {
                    var edge = edges[i];
                    if (edge.source().id() === node.id() && edge.data('sourcePort') === portNum) {
                        return true;
                    }
                    if (edge.target().id() === node.id() && edge.data('targetPort') === portNum) {
                        return true;
                    }
                }
                return false;
            }
            
            // Manual edge creation and selection - unified node tap handler
            cy.on('tap', 'node', function(evt) {
                var node = evt.target;
                
                // If in connection mode, handle connection logic
                if (connectionMode.active) {
                    if (!connectionMode.sourceNode) {
                        // First click - select source
                        connectionMode.sourceNode = node;
                        node.addClass('connection-source');
                        node.style('border-color', '#00d9ff');
                        node.style('border-width', '5px');
                        console.log('[Cytoscape] Connection mode: Selected source node ' + node.id());
                        return;
                    }
                    
                    // Second click - create edge
                    var sourceNode = connectionMode.sourceNode;
                    var targetNode = node;
                    
                    // Reset visual
                    sourceNode.removeClass('connection-source');
                    sourceNode.style('border-color', '');
                    sourceNode.style('border-width', '');
                    
                    if (sourceNode.same(targetNode)) {
                        console.log('[Cytoscape] Cannot connect node to itself');
                        connectionMode.sourceNode = null;
                        return;
                    }
                    
                    // Prompt for port numbers and create edge
                    var sourcePort = prompt('Enter source port number (1-' + sourceNode.data('ports') + '):', '1');
                    var targetPort = prompt('Enter target port number (1-' + targetNode.data('ports') + '):', '1');
                    
                    connectionMode.sourceNode = null;
                    
                    if (sourcePort && targetPort) {
                        sourcePort = parseInt(sourcePort);
                        targetPort = parseInt(targetPort);
                        
                        // Validate ports
                        if (sourcePort < 1 || sourcePort > sourceNode.data('ports') ||
                        targetPort < 1 || targetPort > targetNode.data('ports')) {
                            alert('Invalid port numbers! Ports must be between 1 and the node\'s port count.');
                            return;
                        }
                        
                        // Check if ports are already in use
                        if (isPortInUse(sourceNode, sourcePort)) {
                            alert('Source port ' + sourcePort + ' is already in use on ' + sourceNode.id());
                            return;
                        }
                        if (isPortInUse(targetNode, targetPort)) {
                            alert('Target port ' + targetPort + ' is already in use on ' + targetNode.id());
                            return;
                        }
                        
                        // Add edge
                        var newEdge = cy.add({
                            group: 'edges',
                            data: {
                                id: sourceNode.id() + ':' + sourcePort + '-' + targetNode.id() + ':' + targetPort,
                                source: sourceNode.id(),
                                target: targetNode.id(),
                                sourcePort: sourcePort,
                                targetPort: targetPort,
                                label: '[' + sourcePort + '] ↔ [' + targetPort + ']'
                            }
                        });
                        
                        console.log('[Cytoscape] Created edge:', newEdge.id());
                        console.log('[Cytoscape] Edge data:', {
                            id: newEdge.id(),
                            source: newEdge.source().id(),
                            target: newEdge.target().id(),
                            sourcePort: newEdge.data('sourcePort'),
                            targetPort: newEdge.data('targetPort')
                        });
                        window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                    }
                    return;  // Don't show properties when in connection mode
                }
                
                // Normal mode - select and show node properties
                cy.elements().unselect();  // Deselect all first
                node.select();  // Select this node
                
                window.cyState.selectedElement = { type: 'node', element: node };
                console.log('[Cytoscape] Tap event - Selected node: ' + node.id());
                console.log('[Cytoscape] Node data:', {
                    id: node.id(),
                    label: node.data('label'),
                    type: node.data('type'),
                    ports: node.data('ports')
                });
                
                // Dispatch event to update properties panel
                showNodeProperties(node);
            });
            
            // Also listen to select event as a backup
            cy.on('select', 'node', function(evt) {
                var node = evt.target;
                console.log('[Cytoscape] Select event - Node selected: ' + node.id());
                window.cyState.selectedElement = { type: 'node', element: node };
                showNodeProperties(node);
            });
            
            // Edge selection handler
            cy.on('tap', 'edge', function(evt) {
                var edge = evt.target;
                
                // Select the edge
                cy.elements().unselect();
                edge.select();
                
                window.cyState.selectedElement = { type: 'edge', element: edge };
                console.log('[Cytoscape] Tap event - Selected edge: ' + edge.id());
                console.log('[Cytoscape] Edge data:', {
                    id: edge.id(),
                    source: edge.source().id(),
                    target: edge.target().id(),
                    sourcePort: edge.data('sourcePort'),
                    targetPort: edge.data('targetPort')
                });
                
                showEdgeProperties(edge);
            });
            
            // Also listen to select event for edges
            cy.on('select', 'edge', function(evt) {
                var edge = evt.target;
                console.log('[Cytoscape] Select event - Edge selected: ' + edge.id());
                window.cyState.selectedElement = { type: 'edge', element: edge };
                showEdgeProperties(edge);
            });
            
            // Background tap - deselect
            cy.on('tap', function(evt) {
                if (evt.target === cy) {
                    cy.elements().unselect();
                    window.cyState.selectedElement = null;
                    console.log('[Cytoscape] Deselected all (background tap)');
                    showEmptyProperties();
                }
            });
            
            // Old ehcomplete handler (now unused but kept for reference)
            cy.on('ehcomplete', function(event, sourceNode, targetNode, addedEdge) {
                // Prompt for port numbers
                var sourcePort = prompt('Enter source port number (1-' + sourceNode.data('ports') + '):', '1');
                var targetPort = prompt('Enter target port number (1-' + targetNode.data('ports') + '):', '1');
                
                if (sourcePort && targetPort) {
                    sourcePort = parseInt(sourcePort);
                    targetPort = parseInt(targetPort);
                    
                    // Validate ports
                    if (sourcePort < 1 || sourcePort > sourceNode.data('ports') ||
                    targetPort < 1 || targetPort > targetNode.data('ports')) {
                        alert('Invalid port numbers! Ports must be between 1 and the node\'s port count.');
                        cy.remove(addedEdge);
                        return;
                    }
                    
                    // Check if ports are already in use (excluding the current edge being created)
                    cy.remove(addedEdge);  // Temporarily remove to check
                    if (isPortInUse(sourceNode, sourcePort)) {
                        alert('Source port ' + sourcePort + ' is already in use on ' + sourceNode.id());
                        return;
                    }
                    if (isPortInUse(targetNode, targetPort)) {
                        alert('Target port ' + targetPort + ' is already in use on ' + targetNode.id());
                        return;
                    }
                    
                    // Add edge back with proper data
                    var newEdge = cy.add({
                        group: 'edges',
                        data: {
                            id: sourceNode.id() + ':' + sourcePort + '-' + targetNode.id() + ':' + targetPort,
                            source: sourceNode.id(),
                            target: targetNode.id(),
                            sourcePort: sourcePort,
                            targetPort: targetPort,
                            label: '[' + sourcePort + '] ↔ [' + targetPort + ']'
                        }
                    });
                    
                    // No undo/redo for now
                    
                    // Notify change
                    window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                }
            });
            
            // Keyboard shortcuts
            document.addEventListener('keydown', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                
                // Delete key
                if (e.key === 'Delete' || e.key === 'Backspace') {
                    e.preventDefault();
                    var selected = cy.$(':selected');
                    if (selected.length > 0) {
                        selected.remove();
                        window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                        window.dispatchEvent(new CustomEvent('cy-deselect'));
                    }
                }
                
                // Undo (Ctrl+Z)
                if (e.ctrlKey && e.key === 'z') {
                    e.preventDefault();
                    ur.undo();
                    window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                }
                
                // Redo (Ctrl+Y)
                if (e.ctrlKey && e.key === 'y') {
                    e.preventDefault();
                    ur.redo();
                    window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                }
                
                // Fit (Space)
                if (e.key === ' ') {
                    e.preventDefault();
                    cy.fit();
                }
            });
            
            // Export functions for button handlers
            window.cyActions = {
                addSwitch: function() {
                    window.cyState.mode = 'add_switch';
                    cy.autoungrabify(false);
                    connectionMode.active = false;
                    connectionMode.sourceNode = null;
                    
                    
                    // One-time handler for canvas click
                    var handler = function(evt) {
                        if (evt.target === cy) {
                            window.cyState.nodeCounter.Switch++;
                            var newNode = cy.add({
                                group: 'nodes',
                                data: {
                                    id: 'Switch-' + window.cyState.nodeCounter.Switch,
                                    label: 'Switch-' + window.cyState.nodeCounter.Switch,
                                    type: 'Switch',
                                    ports: 32
                                },
                                position: evt.position,
                                classes: 'switch'
                            });
                            
                            console.log('[Cytoscape] Added switch: ' + newNode.id());
                            
                            // Select the new node and show its properties
                            cy.elements().unselect();
                            newNode.select();
                            window.cyState.selectedElement = { type: 'node', element: newNode };
                            showNodeProperties(newNode);
                            
                            window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                            window.cyState.mode = 'select';
                            cy.off('tap', handler);
                        }
                    };
                    cy.on('tap', handler);
                },
                
                addHca: function() {
                    window.cyState.mode = 'add_hca';
                    cy.autoungrabify(false);
                    connectionMode.active = false;
                    connectionMode.sourceNode = null;
                    
                    
                    // One-time handler for canvas click
                    var handler = function(evt) {
                        if (evt.target === cy) {
                            window.cyState.nodeCounter.Hca++;
                            var newNode = cy.add({
                                group: 'nodes',
                                data: {
                                    id: 'Hca-' + window.cyState.nodeCounter.Hca,
                                    label: 'Hca-' + window.cyState.nodeCounter.Hca,
                                    type: 'Hca',
                                    ports: 2
                                },
                                position: evt.position,
                                classes: 'hca'
                            });
                            
                            console.log('[Cytoscape] Added HCA: ' + newNode.id());
                            
                            // Select the new node and show its properties
                            cy.elements().unselect();
                            newNode.select();
                            window.cyState.selectedElement = { type: 'node', element: newNode };
                            showNodeProperties(newNode);
                            
                            window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                            window.cyState.mode = 'select';
                            cy.off('tap', handler);
                        }
                    };
                    cy.on('tap', handler);
                },
                
                toggleConnectMode: function() {
                    if (connectionMode.active) {
                        // Disable connection mode
                        connectionMode.active = false;
                        connectionMode.sourceNode = null;
                        window.cyState.mode = 'select';
                        console.log('[Cytoscape] Connection mode disabled');
                        return false;
                    } else {
                        // Enable connection mode
                        connectionMode.active = true;
                        window.cyState.mode = 'connect';
                        console.log('[Cytoscape] Connection mode enabled - click source node, then target node');
                        return true;
                    }
                },
                
                autoLayout: function() {
                    cy.layout({
                        name: 'breadthfirst',
                        directed: true,
                        padding: 50,
                        spacingFactor: 1.75,
                        avoidOverlap: true,
                        nodeDimensionsIncludeLabels: true,
                        animate: true,
                        animationDuration: 500,
                        roots: function(ele) {
                            var label = ele.data('label').toLowerCase();
                            return label.includes('spine');
                        },
                        depthSort: function(a, b) {
                            var aLabel = a.data('label').toLowerCase();
                            var bLabel = b.data('label').toLowerCase();
                            var aRank = aLabel.includes('spine') ? 1 : (aLabel.includes('leaf') ? 2 : 3);
                            var bRank = bLabel.includes('spine') ? 1 : (bLabel.includes('leaf') ? 2 : 3);
                            if (aRank !== bRank) return aRank - bRank;
                            return aLabel.localeCompare(bLabel);
                        }
                    }).run();
                },
                
                undo: function() {
                    console.warn('[Cytoscape] Undo/redo not available (extension removed for stability)');
                },
                
                redo: function() {
                    console.warn('[Cytoscape] Undo/redo not available (extension removed for stability)');
                },
                
                zoomIn: function() {
                    cy.zoom(cy.zoom() * 1.2);
                },
                
                zoomOut: function() {
                    cy.zoom(cy.zoom() * 0.8);
                },
                
                fit: function() {
                    cy.fit();
                },
                
                updateNode: function(id, newData) {
                    var node = cy.getElementById(id);
                    if (node.length > 0) {
                        // Validate node name uniqueness if changing label
                        if (newData.label && newData.label !== node.id()) {
                            var existing = cy.getElementById(newData.label);
                            if (existing.length > 0) {
                                alert('A node with name "' + newData.label + '" already exists!');
                                return;
                            }
                            
                            // Update node ID along with label
                            var oldId = node.id();
                            var newId = newData.label;
                            
                            console.log('[Cytoscape] Updating node from "' + oldId + '" to "' + newId + '"');
                            
                            // Store edge information before removing the node
                            var edgeInfo = [];
                            node.connectedEdges().forEach(function(edge) {
                                var info = {
                                    id: edge.id(),
                                    source: edge.source().id(),
                                    target: edge.target().id(),
                                    sourcePort: edge.data('sourcePort'),
                                    targetPort: edge.data('targetPort')
                                };
                                
                                // Update source/target to new ID if needed
                                if (info.source === oldId) info.source = newId;
                                if (info.target === oldId) info.target = newId;
                                
                                // Update edge ID
                                info.id = info.source + ':' + info.sourcePort + '-' + info.target + ':' + info.targetPort;
                                
                                edgeInfo.push(info);
                            });
                            
                            // Remove old node (this also removes connected edges)
                            var position = node.position();
                            var nodeType = node.data('type');
                            var classes = node.hasClass('switch') ? 'switch' : 'hca';
                            cy.remove(node);
                            
                            // Add new node with updated ID
                            var updatedNode = cy.add({
                                group: 'nodes',
                                data: {
                                    id: newId,
                                    label: newId,
                                    type: nodeType,
                                    ports: newData.ports || 32
                                },
                                position: position,
                                classes: classes
                            });
                            
                            // Recreate edges with updated node references
                            edgeInfo.forEach(function(info) {
                                cy.add({
                                    group: 'edges',
                                    data: {
                                        id: info.id,
                                        source: info.source,
                                        target: info.target,
                                        sourcePort: info.sourcePort,
                                        targetPort: info.targetPort,
                                        label: '[' + info.sourcePort + '] ↔ [' + info.targetPort + ']'
                                    }
                                });
                            });
                            
                            // Select the updated node and update properties panel
                            cy.elements().unselect();
                            updatedNode.select();
                            window.cyState.selectedElement = { type: 'node', element: updatedNode };
                            
                            // Trigger properties panel update with new node data
                            window.dispatchEvent(new CustomEvent('cy-node-selected', {
                                detail: {
                                    id: newId,
                                    label: newId,
                                    type: nodeType,
                                    ports: newData.ports || 32
                                }
                            }));
                            
                            console.log('[Cytoscape] Node updated successfully from "' + oldId + '" to "' + newId + '"');
                        } else {
                            // Just update ports (no name change)
                            node.data('ports', newData.ports);
                            console.log('[Cytoscape] Updated ports for node "' + id + '" to ' + newData.ports);
                            
                            // Update properties panel to reflect the change
                            window.dispatchEvent(new CustomEvent('cy-node-selected', {
                                detail: {
                                    id: node.id(),
                                    label: node.data('label'),
                                    type: node.data('type'),
                                    ports: newData.ports
                                }
                            }));
                        }
                        
                        window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                    }
                },
                
                deleteNode: function(id) {
                    var node = cy.getElementById(id);
                    if (node.length > 0) {
                        node.remove();
                        window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                        window.dispatchEvent(new CustomEvent('cy-deselect'));
                    }
                },
                
                updateEdge: function(id, newData) {
                    var edge = cy.getElementById(id);
                    if (edge.length > 0) {
                        var sourceNode = edge.source();
                        var targetNode = edge.target();
                        
                        console.log('[Cytoscape] Updating edge: ' + sourceNode.id() + '[' + newData.sourcePort + '] <-> ' + targetNode.id() + '[' + newData.targetPort + ']');
                        
                        // Validate port numbers
                        if (newData.sourcePort < 1 || newData.sourcePort > sourceNode.data('ports')) {
                            alert('Invalid source port! Must be between 1 and ' + sourceNode.data('ports'));
                            return;
                        }
                        if (newData.targetPort < 1 || newData.targetPort > targetNode.data('ports')) {
                            alert('Invalid target port! Must be between 1 and ' + targetNode.data('ports'));
                            return;
                        }
                        
                        // Check if new ports are already in use (excluding this edge)
                        var oldSourcePort = edge.data('sourcePort');
                        var oldTargetPort = edge.data('targetPort');
                        
                        if (newData.sourcePort !== oldSourcePort && isPortInUse(sourceNode, newData.sourcePort)) {
                            alert('Source port ' + newData.sourcePort + ' is already in use!');
                            return;
                        }
                        if (newData.targetPort !== oldTargetPort && isPortInUse(targetNode, newData.targetPort)) {
                            alert('Target port ' + newData.targetPort + ' is already in use!');
                            return;
                        }
                        
                        edge.data(newData);
                        edge.data('label', '[' + newData.sourcePort + '] ↔ [' + newData.targetPort + ']');
                        edge.data('id', sourceNode.id() + ':' + newData.sourcePort + '-' + targetNode.id() + ':' + newData.targetPort);
                        console.log('[Cytoscape] Edge updated successfully');
                        window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                    }
                },
                
                deleteEdge: function(id) {
                    var edge = cy.getElementById(id);
                    if (edge.length > 0) {
                        edge.remove();
                        window.dispatchEvent(new CustomEvent('cy-topology-changed'));
                        window.dispatchEvent(new CustomEvent('cy-deselect'));
                    }
                },
                
                getTopology: function() {
                    var topology = { nodes: [], edges: [] };
                    
                    cy.nodes().forEach(function(node) {
                        var nodeData = {
                            id: node.id(),
                            type: node.data('type'),
                            ports: node.data('ports')
                        };
                        topology.nodes.push(nodeData);
                        console.log('[getTopology] Node:', nodeData);
                    });
                    
                    cy.edges().forEach(function(edge) {
                        var edgeData = {
                            id: edge.id(),
                            source: edge.source().id(),
                            target: edge.target().id(),
                            sourcePort: edge.data('sourcePort'),
                            targetPort: edge.data('targetPort')
                        };
                        topology.edges.push(edgeData);
                        console.log('[getTopology] Edge:', edgeData);
                    });
                    
                    console.log('[getTopology] Returning topology with', topology.nodes.length, 'nodes and', topology.edges.length, 'edges');
                    return topology;
                },
                
                loadTopology: function(elements) {
                    cy.elements().remove();
                    cy.add(elements);
                    cy.layout({
                        name: 'breadthfirst',
                        directed: true,
                        padding: 50,
                        spacingFactor: 1.75,
                        avoidOverlap: true,
                        nodeDimensionsIncludeLabels: true,
                        roots: function(ele) {
                            var label = ele.data('label').toLowerCase();
                            return label.includes('spine');
                        },
                        depthSort: function(a, b) {
                            var aLabel = a.data('label').toLowerCase();
                            var bLabel = b.data('label').toLowerCase();
                            var aRank = aLabel.includes('spine') ? 1 : (aLabel.includes('leaf') ? 2 : 3);
                            var bRank = bLabel.includes('spine') ? 1 : (bLabel.includes('leaf') ? 2 : 3);
                            if (aRank !== bRank) return aRank - bRank;
                            return aLabel.localeCompare(bLabel);
                        }
                    }).run();
                    window.dispatchEvent(new CustomEvent('cy-deselect'));
                }
            };
            
            console.log('[Cytoscape] Successfully initialized!');
            console.log('[Cytoscape] Loaded ' + cy.nodes().length + ' nodes and ' + cy.edges().length + ' edges');
            
            // Debug: Log all edges
            console.log('[Cytoscape] Edge details:');
            cy.edges().forEach(function(edge) {
                console.log('  ' + edge.source().id() + '[' + edge.data('sourcePort') + '] <-> ' +
                edge.target().id() + '[' + edge.data('targetPort') + ']');
            });
            
            // Explicitly run layout to ensure proper hierarchical arrangement
            console.log('[Cytoscape] Running breadthfirst layout...');
            cy.layout({
                name: 'breadthfirst',
                directed: true,
                padding: 50,
                spacingFactor: 1.75,
                avoidOverlap: true,
                nodeDimensionsIncludeLabels: true,
                roots: function(ele) {
                    var label = ele.data('label').toLowerCase();
                    var isRoot = label.includes('spine');
                    if (isRoot) {
                        console.log('[Layout] Root node: ' + label);
                    }
                    return isRoot;
                },
                depthSort: function(a, b) {
                    var aLabel = a.data('label').toLowerCase();
                    var bLabel = b.data('label').toLowerCase();
                    var aRank = aLabel.includes('spine') ? 1 : (aLabel.includes('leaf') ? 2 : 3);
                    var bRank = bLabel.includes('spine') ? 1 : (bLabel.includes('leaf') ? 2 : 3);
                    if (aRank !== bRank) return aRank - bRank;
                    return aLabel.localeCompare(bLabel);
                }
            }).run();
            console.log('[Cytoscape] Layout complete');
            
            // Auto-fit to screen after layout
            setTimeout(function() {
                cy.fit(50);  // 50px padding
                console.log('[Cytoscape] Auto-fitted graph to viewport');
            }, 100);
        } catch (error) {
            console.error('[Cytoscape] Error during initialization:', error);
            console.error('[Cytoscape] Stack trace:', error.stack);
        }
    }
    
    // Expose initWhenReady globally for manual reinitialization
    window.reinitCytoscape = initWhenReady;
    
    // Start initialization
    console.log('[Cytoscape] Starting automatic initialization...');
    initWhenReady();
})();
