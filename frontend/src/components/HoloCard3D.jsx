import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, PresentationControls, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

// ---- Texture de face procédurale (zéro dépendance image externe / CORS) -----
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function faceTexture({ title, sub, price, verdict, accent }) {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 728;
  const ctx = c.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, 60, 728);
  g.addColorStop(0, "#140C28");
  g.addColorStop(0.55, accent);
  g.addColorStop(1, "#E6DBFF");
  ctx.fillStyle = g;
  roundRect(ctx, 0, 0, 512, 728, 36);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,.35)";
  ctx.lineWidth = 5;
  roundRect(ctx, 22, 22, 468, 684, 22);
  ctx.stroke();
  // fenêtre d'art
  ctx.fillStyle = "rgba(0,0,0,.22)";
  roundRect(ctx, 42, 96, 428, 372, 16);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,.22)";
  ctx.lineWidth = 2;
  roundRect(ctx, 42, 96, 428, 372, 16);
  ctx.stroke();
  // titre
  ctx.fillStyle = "#FFFFFF";
  ctx.font = "800 38px Outfit, Arial, sans-serif";
  ctx.fillText((title || "Deal").slice(0, 17), 44, 70);
  ctx.font = "600 20px 'JetBrains Mono', monospace";
  ctx.fillStyle = "rgba(255,255,255,.85)";
  ctx.fillText((sub || "").slice(0, 26), 46, 510);
  // verdict
  if (verdict) {
    ctx.fillStyle = "rgba(255,255,255,.16)";
    roundRect(ctx, 44, 540, 200, 56, 12);
    ctx.fill();
    ctx.fillStyle = "#FFE9A8";
    ctx.font = "800 30px Outfit, Arial, sans-serif";
    ctx.fillText(`★ ${verdict}`, 60, 580);
  }
  // prix
  ctx.fillStyle = "#FFFFFF";
  ctx.font = "800 64px 'JetBrains Mono', monospace";
  ctx.fillText(price || "", 44, 690);
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  return tex;
}

// ---- Shader holographique (iridescence fresnel + scintille, animé) ----------
const HOLO_VERT = `
  varying vec2 vUv; varying vec3 vView; varying vec3 vNormal;
  void main(){
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vView = normalize(-mv.xyz);
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * mv;
  }`;
const HOLO_FRAG = `
  varying vec2 vUv; varying vec3 vView; varying vec3 vNormal;
  uniform float uTime; uniform float uIntensity;
  vec3 hue(float h){ return clamp(abs(mod(h*6.0+vec3(0.,4.,2.),6.)-3.)-1.,0.,1.); }
  float hash(vec2 p){ return fract(sin(dot(p, vec2(41.3,289.1)))*43758.5453); }
  void main(){
    float fres = pow(1.0 - max(dot(vNormal, vView), 0.0), 2.3);
    float band = vUv.x*3.2 + vUv.y*2.0 + uTime*0.18 + fres*2.6;
    vec3 rainbow = hue(fract(band));
    vec2 cell = floor(vUv*70.0);
    float spark = step(0.972, hash(cell + floor(uTime*2.2)));
    vec3 col = rainbow * (fres*0.95 + 0.08) + spark*0.7;
    gl_FragColor = vec4(col * uIntensity, fres*0.85 + spark*0.5);
  }`;

function Holo() {
  const mat = useRef();
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uIntensity: { value: 1.05 } }), []);
  useFrame((s) => { if (mat.current) mat.current.uniforms.uTime.value = s.clock.elapsedTime; });
  return (
    <mesh position={[0, 0, 0.052]}>
      <planeGeometry args={[1.34, 1.94]} />
      <shaderMaterial ref={mat} vertexShader={HOLO_VERT} fragmentShader={HOLO_FRAG}
        uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
    </mesh>
  );
}

function Glare() {
  const light = useRef();
  useFrame((s) => {
    if (!light.current) return;
    light.current.position.x = Math.sin(s.clock.elapsedTime * 0.8) * 3;
    light.current.position.y = Math.cos(s.clock.elapsedTime * 0.6) * 2 + 1;
  });
  return <pointLight ref={light} position={[2, 2, 3]} intensity={2.4} color="#ffffff" />;
}

function Card({ accent, ...info }) {
  const tex = useMemo(() => faceTexture({ accent, ...info }), [accent, info.title, info.price, info.verdict, info.sub]);
  return (
    <group>
      <RoundedBox args={[1.42, 2.02, 0.09]} radius={0.07} smoothness={5} castShadow>
        <meshStandardMaterial color={accent} metalness={0.65} roughness={0.28} />
      </RoundedBox>
      <mesh position={[0, 0, 0.05]}>
        <planeGeometry args={[1.36, 1.96]} />
        <meshStandardMaterial map={tex} metalness={0.25} roughness={0.55} />
      </mesh>
      <Holo />
    </group>
  );
}

export default function HoloCard3D({ accent = "#5B3FA8", height = 340, ...info }) {
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 0, 4.2], fov: 34 }}
      gl={{ antialias: true, alpha: true }} style={{ height, touchAction: "none" }}>
      <ambientLight intensity={0.65} />
      <directionalLight position={[3, 5, 4]} intensity={1.1} />
      <Glare />
      <PresentationControls global snap rotation={[0, 0, 0]}
        polar={[-0.5, 0.5]} azimuth={[-0.9, 0.9]} config={{ mass: 1.1, tension: 200, friction: 26 }}>
        <Float speed={2.2} rotationIntensity={0.45} floatIntensity={0.7}>
          <Card accent={accent} {...info} />
        </Float>
      </PresentationControls>
    </Canvas>
  );
}
