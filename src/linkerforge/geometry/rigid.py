"""Rigid-body algebra needed to place one domain relative to another.

Pure standard library on purpose: the geometry package has to run on a laptop
with no torch, numpy or compiler, unlike ``linkerforge.models``.

The optimal-rotation solver is Horn's quaternion method, with the eigenvector
found by cyclic Jacobi rotations on the symmetric 4x4 matrix:

  Horn, B. K. P. (1987). Closed-form solution of absolute orientation using
  unit quaternions. Journal of the Optical Society of America A, 4(4), 629-642.
  https://doi.org/10.1364/JOSAA.4.000629
"""

from __future__ import annotations

from math import cos, sin, sqrt

Point = tuple[float, float, float]
Matrix3 = tuple[Point, Point, Point]

IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def centroid(points: tuple[Point, ...]) -> Point:
    if not points:
        raise ValueError("Cannot take the centroid of no points")
    count = len(points)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def apply(rotation: Matrix3, translation: Point, point: Point) -> Point:
    return (
        rotation[0][0] * point[0] + rotation[0][1] * point[1] + rotation[0][2] * point[2] + translation[0],
        rotation[1][0] * point[0] + rotation[1][1] * point[1] + rotation[1][2] * point[2] + translation[1],
        rotation[2][0] * point[0] + rotation[2][1] * point[1] + rotation[2][2] * point[2] + translation[2],
    )


def rotation_from_quaternion(quaternion: tuple[float, float, float, float]) -> Matrix3:
    """Rotation matrix of a quaternion given as (w, x, y, z)."""
    norm = sqrt(sum(component * component for component in quaternion))
    if norm == 0:
        raise ValueError("Zero quaternion has no rotation")
    w, x, y, z = (component / norm for component in quaternion)
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def quaternion_from_axis_angle(axis: Point, angle: float) -> tuple[float, float, float, float]:
    length = sqrt(sum(component * component for component in axis))
    if length == 0:
        raise ValueError("Rotation axis cannot be zero")
    unit = tuple(component / length for component in axis)
    half = angle / 2.0
    s = sin(half)
    return (cos(half), unit[0] * s, unit[1] * s, unit[2] * s)


def _jacobi_eigen(matrix: list[list[float]], sweeps: int = 100) -> tuple[list[float], list[list[float]]]:
    """Eigenvalues and eigenvectors (as columns) of a small symmetric matrix."""
    size = len(matrix)
    a = [row[:] for row in matrix]
    vectors = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
    for _ in range(sweeps):
        off_diagonal = sum(a[i][j] * a[i][j] for i in range(size) for j in range(i + 1, size))
        if off_diagonal < 1e-20:
            break
        for p in range(size - 1):
            for q in range(p + 1, size):
                if abs(a[p][q]) < 1e-18:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                sign = 1.0 if theta >= 0 else -1.0
                t = sign / (abs(theta) + sqrt(theta * theta + 1.0))
                c = 1.0 / sqrt(t * t + 1.0)
                s = t * c
                for k in range(size):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(size):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(size):
                    vkp, vkq = vectors[k][p], vectors[k][q]
                    vectors[k][p] = c * vkp - s * vkq
                    vectors[k][q] = s * vkp + c * vkq
    return [a[i][i] for i in range(size)], vectors


def optimal_superposition(
    moving: tuple[Point, ...],
    target: tuple[Point, ...],
) -> tuple[Matrix3, Point]:
    """Rotation and translation that best map ``moving`` onto ``target``.

    Least-squares optimal over all rigid motions (no reflection), by Horn's
    quaternion method. Three or more non-collinear point pairs give a unique
    answer; fewer are accepted and simply leave rotations about the remaining
    degrees of freedom unconstrained.
    """
    if len(moving) != len(target):
        raise ValueError("Point sets differ in length")
    if not moving:
        raise ValueError("Cannot superpose empty point sets")
    moving_centre = centroid(moving)
    target_centre = centroid(target)
    s = [[0.0] * 3 for _ in range(3)]
    for p, q in zip(moving, target):
        pc = (p[0] - moving_centre[0], p[1] - moving_centre[1], p[2] - moving_centre[2])
        qc = (q[0] - target_centre[0], q[1] - target_centre[1], q[2] - target_centre[2])
        for i in range(3):
            for j in range(3):
                s[i][j] += pc[i] * qc[j]
    sxx, sxy, sxz = s[0]
    syx, syy, syz = s[1]
    szx, szy, szz = s[2]
    n = [
        [sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
        [syz - szy, sxx - syy - szz, sxy + syx, szx + sxz],
        [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
        [sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz],
    ]
    values, vectors = _jacobi_eigen(n)
    best = max(range(4), key=lambda index: values[index])
    quaternion = (
        vectors[0][best],
        vectors[1][best],
        vectors[2][best],
        vectors[3][best],
    )
    rotation = rotation_from_quaternion(quaternion)
    rotated_centre = apply(rotation, (0.0, 0.0, 0.0), moving_centre)
    translation = (
        target_centre[0] - rotated_centre[0],
        target_centre[1] - rotated_centre[1],
        target_centre[2] - rotated_centre[2],
    )
    return rotation, translation
