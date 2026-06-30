import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import * as THREE from "three";

// ---- Texture de carte procédurale (pas d'image externe / CORS) --------------
function cardTexture({ name, tier, tierColor, value, accent }) {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 358;
  const ctx = c.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, 40, 358);
  g.addColorStop(0, "#120A26");
  g.addColorStop(0.55, accent);
  g.addColorStop(1, "#EBE2FF");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 358);
  ctx.strokeStyle = "rgba(255,255,255,.35)";
  ctx.lineWidth = 3;
  ctx.strokeRect(10, 10, 236, 338);
  ctx.fillStyle = "rgba(0,0,0,.2)";
  ctx.fillRect(22, 46, 212, 176);
  ctx.fillStyle = "#fff";
  ctx.font = "800 22px Outfit, Arial, sans-serif";
  ctx.fillText((name || "").slice(0, 15), 22, 36);
  ctx.fillStyle = tierColor || "#C9B8FF";
  ctx.font = "700 14px 'JetBrains Mono', monospace";
  ctx.fillText(tier || "", 22, 252);
  ctx.fillStyle = "#fff";
  ctx.font = "800 40px 'JetBrains Mono', monospace";
  ctx.fillText(value || "", 22, 330);
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  return tex;
}

const HOLO_VERT = `
  varying vec3 vView; varying vec3 vN; varying vec2 vUv;
  void main(){ vUv=uv; vec4 mv=modelViewMatrix*vec4(position,1.0); vView=normalize(-mv.xyz); vN=normalize(normalMatrix*normal); gl_Position=projectionMatrix*mv; }`;
const HOLO_FRAG = `
  varying vec3 vView; varying vec3 vN; varying vec2 vUv; uniform float uTime;
  vec3 hue(float h){ return clamp(abs(mod(h*6.0+vec3(0.,4.,2.),6.)-3.)-1.,0.,1.); }
  void main(){ float f=pow(1.0-max(dot(vN,vView),0.0),2.3); vec3 r=hue(fract(vUv.x*3.0+vUv.y*2.0+uTime*0.2+f*2.5)); gl_FragColor=vec4(r*(f*0.9+0.1),f*0.8); }`;

function holoUniforms() {
  return { uTime: { value: 0 } };
}

// ---- Carte projetée (ressort + vitesse initiale = effet « physique ») -------
function FlyCard({ data, index, total, fire }) {
  const group = useRef();
  const holo = useRef();
  const pos = useRef(new THREE.Vector3(0, 0, index * 0.04));
  const vel = useRef(
    new THREE.Vector3((index - (total - 1) / 2) * 2.2 + (Math.random() - 0.5) * 2, 4 + Math.random() * 3.5, Math.random() * 2 + 1.5)
  );
  const rot = useRef(new THREE.Vector3(Math.random() * 4, Math.random() * 4, (Math.random() - 0.5) * 4));
  const aVel = useRef(new THREE.Vector3((Math.random() - 0.5) * 8, (Math.random() - 0.5) * 8, (Math.random() - 0.5) * 10));
  const target = useMemo(() => {
    const c = (total - 1) / 2;
    return new THREE.Vector3((index - c) * 1.02, -Math.abs(index - c) * 0.16 + 0.1, index * 0.04);
  }, [index, total]);
  const targetRot = useMemo(() => new THREE.Vector3(0, 0, ((index - (total - 1) / 2) * -0.14)), [index, total]);
  const tex = useMemo(() => cardTexture(data), [data]);
  const uniforms = useMemo(holoUniforms, []);

  useFrame((state, dt) => {
    if (!group.current || !fire) return;
    dt = Math.min(dt, 0.05);
    const K = 30, D = 10;
    // ressort position (avec vitesse initiale → burst puis amorti)
    const acc = target.clone().sub(pos.current).multiplyScalar(K).addScaledVector(vel.current, -D);
    vel.current.addScaledVector(acc, dt);
    pos.current.addScaledVector(vel.current, dt);
    // ressort rotation
    const aAcc = targetRot.clone().sub(rot.current).multiplyScalar(K).addScaledVector(aVel.current, -D);
    aVel.current.addScaledVector(aAcc, dt);
    rot.current.addScaledVector(aVel.current, dt);
    group.current.position.copy(pos.current);
    group.current.rotation.set(rot.current.x, rot.current.y, rot.current.z);
    if (holo.current) holo.current.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return (
    <group ref={group}>
      <mesh>
        <planeGeometry args={[0.74, 1.04]} />
        <meshStandardMaterial map={tex} metalness={0.3} roughness={0.5} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0, 0.001]}>
        <planeGeometry args={[0.74, 1.04]} />
        <shaderMaterial ref={holo} vertexShader={HOLO_VERT} fragmentShader={HOLO_FRAG}
          uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

// ---- Le booster : deux moitiés qui se déchirent ----------------------------
function PackBody({ ripped, onRip, accent }) {
  const grp = useRef();
  const top = useRef();
  const bot = useRef();
  const holo = useRef();
  const p = useRef(0);
  const uniforms = useMemo(holoUniforms, []);

  useFrame((state, dt) => {
    const tEl = state.clock.elapsedTime;
    if (holo.current) holo.current.uniforms.uTime.value = tEl;
    if (!ripped) {
      if (grp.current) grp.current.position.y = Math.sin(tEl * 1.6) * 0.08; // flottement
      if (grp.current) grp.current.rotation.y = Math.sin(tEl * 0.5) * 0.3;
      return;
    }
    p.current = Math.min(1, p.current + Math.min(dt, 0.05) * 1.7);
    const e = 1 - Math.pow(1 - p.current, 3);
    if (top.current) {
      top.current.position.y = 0.56 + e * 1.7;
      top.current.rotation.z = e * 0.7;
      top.current.material.opacity = 1 - e;
    }
    if (bot.current) {
      bot.current.position.y = -0.56 - e * 1.5;
      bot.current.rotation.z = -e * 0.6;
      bot.current.material.opacity = 1 - e;
    }
    if (holo.current) holo.current.material && (holo.current.material.opacity = 1 - e);
  });

  return (
    <group ref={grp} onClick={(e) => { e.stopPropagation(); if (!ripped) onRip(); }}>
      <mesh ref={top} position={[0, 0.56, 0]}>
        <boxGeometry args={[1.4, 1.12, 0.16]} />
        <meshStandardMaterial color={accent} metalness={0.6} roughness={0.3} transparent />
      </mesh>
      <mesh ref={bot} position={[0, -0.56, 0]}>
        <boxGeometry args={[1.4, 1.12, 0.16]} />
        <meshStandardMaterial color={accent} metalness={0.6} roughness={0.3} transparent />
      </mesh>
      <mesh ref={holo} position={[0, 0, 0.09]}>
        <planeGeometry args={[1.4, 2.24]} />
        <shaderMaterial vertexShader={HOLO_VERT} fragmentShader={HOLO_FRAG}
          uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

function Glare() {
  const ref = useRef();
  useFrame((s) => {
    if (!ref.current) return;
    ref.current.position.x = Math.sin(s.clock.elapsedTime) * 4;
    ref.current.position.y = Math.cos(s.clock.elapsedTime * 0.7) * 3 + 1;
  });
  return <pointLight ref={ref} intensity={2.6} color="#ffffff" />;
}

export default function PackOpen3D({ cards, ripped, onRip, accent = "#3D7BFF" }) {
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 0, 6], fov: 38 }}
      gl={{ antialias: true, alpha: true }} style={{ height: 460, touchAction: "none" }}>
      <ambientLight intensity={0.7} />
      <directionalLight position={[3, 5, 4]} intensity={1.1} />
      <Glare />
      <PackBody ripped={ripped} onRip={onRip} accent={accent} />
      {ripped && cards.map((c, i) => (
        <FlyCard key={c.id} data={c} index={i} total={cards.length} fire={ripped} />
      ))}
    </Canvas>
  );
}
