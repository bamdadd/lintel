import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react';
import styles from './DagCanvas.module.css';

export function AnimatedEdge(props: EdgeProps) {
  const {
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
    style,
    markerEnd,
    label,
  } = props;

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={style}
        className={styles.animatedEdge}
      />
      {label && (
        <text
          x={labelX}
          y={labelY}
          className={styles.edgeLabel}
          textAnchor="middle"
          dominantBaseline="central"
        >
          {String(label)}
        </text>
      )}
    </>
  );
}
