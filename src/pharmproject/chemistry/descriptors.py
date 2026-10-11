"""Дескрипторы молекул на RDKit (CPU).

nvMolKit (GPU) — отдельный бэкенд, добавим позже для Linux-машин с NVIDIA GPU.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, QED, rdMolDescriptors


@dataclass(frozen=True)
class DescriptorSet:
    mw: float
    logp: float
    hbd: int
    hba: int
    tpsa: float
    rot_bonds: int
    qed: float


def compute_descriptors(mol: Chem.Mol) -> DescriptorSet:
    """Считает физико-химические дескрипторы для готового RDKit-мола.

    HBD/HBA — стандартные RDKit-дескрипторы NumHDonors / NumHAcceptors.
    """
    return DescriptorSet(
        mw=Descriptors.MolWt(mol),
        logp=Crippen.MolLogP(mol),
        hbd=Descriptors.NumHDonors(mol),
        hba=Descriptors.NumHAcceptors(mol),
        tpsa=rdMolDescriptors.CalcTPSA(mol),
        rot_bonds=rdMolDescriptors.CalcNumRotatableBonds(mol),
        qed=QED.qed(mol),
    )


def parse_and_describe(smiles: str) -> tuple[str, str, DescriptorSet] | None:
    """Парсит SMILES и возвращает (canonical_smiles, inchi_key, descriptors).

    Возвращает None, если SMILES невалидный или не удаётся канонизировать
    (в т.ч. KekulizeException на необычных кольцах — встречается в PubChem).
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None or mol.GetNumAtoms() == 0:
            return None
        canonical = Chem.MolToSmiles(mol)
        inchi_key = Chem.MolToInchiKey(mol)
        return canonical, inchi_key, compute_descriptors(mol)
    except Exception:
        return None
