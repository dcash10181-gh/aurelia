/**
 * HoloCore — the agent's visual presence.
 *
 * A real-time WebGL artifact, not a baked render: an icosahedron wireframe
 * "brain" inside a Fresnel-lit glass shell, orbited by a particle field, with
 * a ground reflection. Everything reacts to agent state, because the whole
 * point of a movie-grade agent UI is that the visuals ARE the state readout —
 * idle breathes slow, thinking spins up and turns gold, tool routing pulses
 * teal, error flares red. Procedural throughout (no asset pipeline), so it
 * stays local-first and reacts instantly to props.
 *
 * Post-processing (the "movie grade" layer): an HDR bloom pass whose strength
 * is itself a state channel — idle glows softly, thinking burns brighter,
 * error flares hard — plus a subtle radial chromatic aberration. The final
 * composite derives canvas alpha from luminance: this scene is pure
 * glow-on-black, so brightness IS coverage, which lets bloom coexist with the
 * transparent canvas over the CSS observatory backdrop (UnrealBloomPass would
 * otherwise force an opaque black canvas and erase the stage's grid/vignette).
 *
 * Built on three.js with hand-rolled animation rather than react-three-fiber:
 * one dependency, full control of the render loop, and no reconciler overhead
 * on a 60fps scene.
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";

export type AgentState = "idle" | "thinking" | "tool" | "error";

// State → visual identity. Colors are the AURELIA palette (gold/teal/bronze)
// pushed to luminance that reads as "emissive hologram" rather than flat fill.
// `bloom` is the post-fx glow strength — a first-class state channel, eased
// like the rest so transitions feel like power ramping, not a light switch.
// Exported so tests can pin the contract without a WebGL context.
export const STATE_STYLE: Record<
  AgentState,
  { core: number; glow: number; spin: number; pulse: number; bloom: number }
> = {
  idle:     { core: 0xe8c476, glow: 0x9a7b3f, spin: 0.15, pulse: 0.6, bloom: 0.65 },
  thinking: { core: 0xffd98a, glow: 0xe8c476, spin: 1.1,  pulse: 2.2, bloom: 1.25 },
  tool:     { core: 0x5fa8a0, glow: 0x5fa8a0, spin: 0.7,  pulse: 1.6, bloom: 0.95 },
  error:    { core: 0xe06b6b, glow: 0xb84a4a, spin: 0.4,  pulse: 3.0, bloom: 1.7 },
};

/**
 * Final composite: radial chromatic aberration + alpha-from-luminance.
 * Runs after OutputPass (so it sees display-referred sRGB values) and renders
 * to screen. Alpha = max channel: bright hologram pixels are opaque, dark
 * pixels transparent, so the page's CSS backdrop shows through untouched.
 * Exported for shader-contract tests.
 */
export const HoloCompositeShader = {
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    uChroma: { value: 0.0075 },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uChroma;
    varying vec2 vUv;
    void main() {
      // Radial aberration: zero at center, grows quadratically to the edges —
      // reads as lens physics rather than a broken display.
      vec2 c = vUv - 0.5;
      vec2 off = c * dot(c, c) * uChroma;
      float r = texture2D(tDiffuse, vUv + off).r;
      float g = texture2D(tDiffuse, vUv).g;
      float b = texture2D(tDiffuse, vUv - off).b;
      vec3 col = vec3(r, g, b);
      // Brightness IS coverage in a glow-on-black scene. The 1.15 lift keeps
      // mid-glow from going too ghostly over the backdrop.
      float a = clamp(max(col.r, max(col.g, col.b)) * 1.15, 0.0, 1.0);
      gl_FragColor = vec4(col, a);
    }`,
};

export function HoloCore({ state }: { state: AgentState }) {
  const mountRef = useRef<HTMLDivElement>(null);
  // Mutable target the render loop reads; updated when `state` changes without
  // tearing down the scene.
  const targetRef = useRef(STATE_STYLE[state]);
  targetRef.current = STATE_STYLE[state];

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const W = mount.clientWidth;
    const H = mount.clientHeight || 360;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
    camera.position.set(0, 0.6, 5.2);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      return; // No WebGL: caller falls back to the SVG halo.
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x000000, 0); // transparent over the CSS stage
    mount.appendChild(renderer.domElement);

    // --- the wireframe "brain": an icosahedron whose vertices we'll perturb
    const coreGeo = new THREE.IcosahedronGeometry(1, 2);
    const basePositions = coreGeo.attributes.position.array.slice();
    const coreMat = new THREE.MeshBasicMaterial({
      color: STATE_STYLE[state].core, wireframe: true, transparent: true, opacity: 0.9,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    scene.add(core);

    // --- glass shell with a Fresnel rim (the "containment field" look)
    const shellGeo = new THREE.IcosahedronGeometry(1.5, 3);
    const shellMat = new THREE.ShaderMaterial({
      transparent: true,
      uniforms: {
        uColor: { value: new THREE.Color(STATE_STYLE[state].glow) },
        uOpacity: { value: 0.35 },
      },
      vertexShader: `
        varying vec3 vN; varying vec3 vView;
        void main() {
          vN = normalize(normalMatrix * normal);
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vView = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uColor; uniform float uOpacity;
        varying vec3 vN; varying vec3 vView;
        void main() {
          float fres = pow(1.0 - max(dot(vN, vView), 0.0), 3.0);
          gl_FragColor = vec4(uColor, fres * uOpacity);
        }`,
    });
    const shell = new THREE.Mesh(shellGeo, shellMat);
    scene.add(shell);

    // --- orbiting particle field
    const COUNT = 900;
    const pPos = new Float32Array(COUNT * 3);
    const pRad: number[] = [];
    const pSpeed: number[] = [];
    const pPhase: number[] = [];
    for (let i = 0; i < COUNT; i++) {
      const r = 2.0 + Math.random() * 1.8;
      const theta = Math.random() * Math.PI * 2;
      const y = (Math.random() - 0.5) * 2.4;
      pRad.push(r); pSpeed.push(0.2 + Math.random() * 0.6); pPhase.push(theta);
      pPos[i * 3] = Math.cos(theta) * r;
      pPos[i * 3 + 1] = y;
      pPos[i * 3 + 2] = Math.sin(theta) * r;
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
    const pMat = new THREE.PointsMaterial({
      color: STATE_STYLE[state].core, size: 0.025, transparent: true,
      opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    // --- ground reflection plane (faint mirrored glow)
    const ringGeo = new THREE.RingGeometry(1.6, 2.4, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: STATE_STYLE[state].glow, transparent: true, opacity: 0.12,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -1.7;
    scene.add(ring);

    // --- post-processing chain.
    // HDR half-float target so bloom has real headroom, and 4x MSAA because
    // EffectComposer bypasses the canvas's built-in antialiasing (wireframes
    // would go jaggy without it). three r163+ is WebGL2-only, so `samples`
    // is safe wherever the renderer constructed at all.
    const rt = new THREE.WebGLRenderTarget(W, H, {
      type: THREE.HalfFloatType,
      samples: 4,
    });
    const composer = new EffectComposer(renderer, rt);
    composer.addPass(new RenderPass(scene, camera));
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(W, H),
      STATE_STYLE[state].bloom, // strength — animated per state below
      0.55,                     // radius — soft halo, not fog
      0.15,                     // threshold — faint ring stays crisp
    );
    composer.addPass(bloomPass);
    composer.addPass(new OutputPass()); // linear→sRGB, matches pre-composer look
    const compositePass = new ShaderPass(HoloCompositeShader);
    composer.addPass(compositePass);

    const coreColor = new THREE.Color(STATE_STYLE[state].core);
    const glowColor = new THREE.Color(STATE_STYLE[state].glow);
    let spin = STATE_STYLE[state].spin;
    let pulse = STATE_STYLE[state].pulse;
    let bloom = STATE_STYLE[state].bloom;

    const clock = new THREE.Clock();
    let raf = 0;
    const corePos = coreGeo.attributes.position;

    const render = () => {
      const t = clock.getElapsedTime();
      const tgt = targetRef.current;

      // Ease visual params toward the current state's targets (smooth, not snappy).
      const k = reduceMotion ? 1 : 0.05;
      coreColor.lerp(new THREE.Color(tgt.core), k);
      glowColor.lerp(new THREE.Color(tgt.glow), k);
      spin += (tgt.spin - spin) * k;
      pulse += (tgt.pulse - pulse) * k;
      bloom += (tgt.bloom - bloom) * k;

      coreMat.color.copy(coreColor);
      pMat.color.copy(coreColor);
      (shellMat.uniforms.uColor.value as THREE.Color).copy(glowColor);
      ringMat.color.copy(glowColor);

      // Bloom breathes with the pulse — the glow is alive, not a constant.
      // Reduced motion gets the state's static strength (color/glow still
      // communicate state; nothing oscillates).
      bloomPass.strength = reduceMotion ? bloom : bloom * (1 + Math.sin(t * pulse) * 0.08);

      if (!reduceMotion) {
        // Vertex displacement: the brain "breathes" and ripples by pulse rate.
        for (let i = 0; i < corePos.count; i++) {
          const ix = i * 3;
          const bx = basePositions[ix], by = basePositions[ix + 1], bz = basePositions[ix + 2];
          const n = Math.sin(t * pulse + bx * 3 + by * 2 + bz) * 0.04;
          const s = 1 + n;
          corePos.setXYZ(i, bx * s, by * s, bz * s);
        }
        corePos.needsUpdate = true;

        core.rotation.y += spin * 0.01;
        core.rotation.x = Math.sin(t * 0.3) * 0.15;
        shell.rotation.y -= spin * 0.004;
        particles.rotation.y += spin * 0.002;

        // Particles drift along their orbits.
        const arr = pGeo.attributes.position.array as Float32Array;
        for (let i = 0; i < COUNT; i++) {
          const ang = pPhase[i] + t * pSpeed[i] * 0.15;
          arr[i * 3] = Math.cos(ang) * pRad[i];
          arr[i * 3 + 2] = Math.sin(ang) * pRad[i];
        }
        pGeo.attributes.position.needsUpdate = true;

        const breathe = 1 + Math.sin(t * pulse * 0.5) * 0.04;
        core.scale.setScalar(breathe);
      }

      composer.render();
      raf = requestAnimationFrame(render);
    };
    render();

    const onResize = () => {
      const w = mount.clientWidth, h = mount.clientHeight || 360;
      camera.aspect = w / h; camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      composer.setSize(w, h); // resizes the HDR target and every pass with it
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      composer.dispose(); // releases the HDR target + bloom's internal RTs
      bloomPass.dispose();
      compositePass.material.dispose();
      renderer.dispose();
      coreGeo.dispose(); shellGeo.dispose(); pGeo.dispose();
      ringGeo.dispose(); coreMat.dispose(); shellMat.dispose();
      pMat.dispose(); ringMat.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []); // scene built once; state changes flow through targetRef

  return <div ref={mountRef} className="h-[360px] w-full" aria-hidden="true" />;
}
