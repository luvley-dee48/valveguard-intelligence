import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Lightformer } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const STEEL = "#8b97a8";
const DARK = "#3a4452";
const CYAN = "#4fd8eb";

function Pipe({ x }: { x: number }) {
  return (
    <group position={[x, 0, 0]}>
      <mesh rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.32, 0.32, 3, 32]} />
        <meshStandardMaterial color={STEEL} metalness={0.85} roughness={0.35} />
      </mesh>
      {[-1.45, 1.45].map((o) => (
        <mesh key={o} position={[o, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.5, 0.5, 0.12, 32]} />
          <meshStandardMaterial color={DARK} metalness={0.9} roughness={0.4} />
        </mesh>
      ))}
    </group>
  );
}

function Flow() {
  const count = 60;
  const ref = useRef<THREE.InstancedMesh>(null);
  const seeds = useMemo(() => Array.from({ length: count }, (_, i) => ({ o: i / count, y: (((i * 37) % 10) / 10 - 0.5) * 0.36, z: (((i * 53) % 10) / 10 - 0.5) * 0.36 })), []);
  const m = useMemo(() => new THREE.Object3D(), []);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.elapsedTime * 0.15;
    seeds.forEach((s, i) => {
      const p = (s.o + t) % 1;
      m.position.set(-4.2 + p * 8.4, s.y, s.z + 0.0);
      m.scale.setScalar(Math.sin(p * Math.PI) * 1);
      m.updateMatrix();
      ref.current!.setMatrixAt(i, m.matrix);
    });
    ref.current.instanceMatrix.needsUpdate = true;
  });
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <sphereGeometry args={[0.035, 8, 8]} />
      <meshBasicMaterial color={CYAN} transparent opacity={0.9} />
    </instancedMesh>
  );
}

function Sensor({ position, phase }: { position: [number, number, number]; phase: number }) {
  const ring = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (!ring.current) return;
    const p = (clock.elapsedTime * 0.5 + phase) % 1;
    ring.current.scale.setScalar(1 + p * 2.5);
    (ring.current.material as THREE.MeshBasicMaterial).opacity = 0.6 * (1 - p);
  });
  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[0.09, 16, 16]} />
        <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={1.5} />
      </mesh>
      <mesh ref={ring}>
        <sphereGeometry args={[0.1, 16, 16]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.5} depthWrite={false} />
      </mesh>
    </group>
  );
}

function Valve() {
  const root = useRef<THREE.Group>(null);
  const wheel = useRef<THREE.Group>(null);
  useFrame(({ pointer }, delta) => {
    const dt = Math.min(delta, 0.05);
    if (wheel.current) wheel.current.rotation.y += dt * 0.35;
    if (root.current) {
      const scroll = Math.min(window.scrollY / 800, 1);
      const ty = -0.5 + pointer.x * 0.25 + scroll * 0.6;
      const tx = 0.18 - pointer.y * 0.12;
      root.current.rotation.y += (ty - root.current.rotation.y) * (1 - Math.exp(-4 * dt));
      root.current.rotation.x += (tx - root.current.rotation.x) * (1 - Math.exp(-4 * dt));
      const s = 1 - scroll * 0.12;
      root.current.scale.setScalar(s);
    }
  });
  return (
    <group ref={root}>
      <Pipe x={-2.6} />
      <Pipe x={2.6} />
      {/* body */}
      <mesh scale={[1.1, 0.95, 0.95]}>
        <sphereGeometry args={[0.9, 48, 48]} />
        <meshStandardMaterial color={STEEL} metalness={0.9} roughness={0.28} />
      </mesh>
      {[-1.05, 1.05].map((x) => (
        <mesh key={x} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.55, 0.55, 0.18, 32]} />
          <meshStandardMaterial color={DARK} metalness={0.9} roughness={0.35} />
        </mesh>
      ))}
      {/* bonnet + stem */}
      <mesh position={[0, 1.0, 0]}>
        <cylinderGeometry args={[0.32, 0.45, 0.5, 32]} />
        <meshStandardMaterial color={DARK} metalness={0.85} roughness={0.4} />
      </mesh>
      <mesh position={[0, 1.6, 0]}>
        <cylinderGeometry args={[0.07, 0.07, 0.9, 16]} />
        <meshStandardMaterial color={STEEL} metalness={1} roughness={0.2} />
      </mesh>
      {/* actuator */}
      <group ref={wheel} position={[0, 2.15, 0]}>
        <mesh>
          <cylinderGeometry args={[0.95, 0.95, 0.35, 48]} />
          <meshStandardMaterial color="#2a323d" metalness={0.7} roughness={0.45} />
        </mesh>
        <mesh position={[0, 0.25, 0]}>
          <sphereGeometry args={[0.95, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2]} />
          <meshStandardMaterial color="#323c48" metalness={0.75} roughness={0.4} />
        </mesh>
        {Array.from({ length: 12 }, (_, i) => (
          <mesh key={i} position={[Math.cos((i / 12) * Math.PI * 2) * 0.97, 0, Math.sin((i / 12) * Math.PI * 2) * 0.97]}>
            <boxGeometry args={[0.06, 0.3, 0.06]} />
            <meshStandardMaterial color={STEEL} metalness={1} roughness={0.25} />
          </mesh>
        ))}
        <mesh position={[0, 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.97, 0.015, 8, 64]} />
          <meshBasicMaterial color={CYAN} />
        </mesh>
      </group>
      <Flow />
      <Sensor position={[-2.2, 0.42, 0]} phase={0} />
      <Sensor position={[2.4, 0.42, 0]} phase={0.33} />
      <Sensor position={[0.75, 2.2, 0.6]} phase={0.66} />
    </group>
  );
}

export default function HeroScene() {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 1.4, 8.2], fov: 38 }}
      gl={{ antialias: true, powerPreference: "low-power" }}
      onCreated={({ gl }) => gl.domElement.parentElement?.parentElement?.setAttribute("data-scene-ready", "true")}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[4, 6, 5]} intensity={1.6} />
      <pointLight position={[-4, -1, 3]} intensity={8} color={CYAN} />
      <Environment resolution={128}>
        <Lightformer intensity={2} position={[0, 5, 0]} scale={[10, 10, 1]} rotation-x={Math.PI / 2} />
        <Lightformer intensity={1.2} color="#7fd" position={[-5, 1, -1]} rotation-y={Math.PI / 2} scale={[20, 1, 1]} />
        <Lightformer intensity={0.8} position={[5, 0, 2]} rotation-y={-Math.PI / 2} scale={[10, 2, 1]} />
      </Environment>
      <group position={[0, -0.6, 0]}>
        <Valve />
      </group>
    </Canvas>
  );
}
