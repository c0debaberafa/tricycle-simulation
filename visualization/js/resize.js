export function initializeResize() {
    const container = document.querySelector('.tabbed-container');
    const handle = document.querySelector('.resize-handle');
    let startY;
    let startHeight;

    function onMouseDown(e) {
        startY = e.clientY;
        startHeight = parseInt(document.defaultView.getComputedStyle(container).height, 10);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    function onMouseMove(e) {
        const newHeight = startHeight - (e.clientY - startY);
        if (newHeight >= 100 && newHeight <= window.innerHeight * 0.8) {
            container.style.height = `${newHeight}px`;
        }
    }

    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }

    handle.addEventListener('mousedown', onMouseDown);
}

// Initialize resize functionality when the DOM is loaded
document.addEventListener('DOMContentLoaded', initializeResize); 