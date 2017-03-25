# Copyright 2016 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from itertools import chain

from moldesign import utils
from moldesign import units as u
from .atomcollections import AtomListOperationMixin
from .biounits import Instance


class MolecularBaseList(utils.AutoIndexList):
    """ Base class for a list of objects (atoms, residues, etc.) in a molecule
    """
    def __init__(self, objs, mol):
        super(MolecularBaseList, self).__init__(objs)
        self._mol = mol

    def _error_if_object_owned(self, obj):
        if obj.molecule is self._mol:
            assert obj in self
            raise ValueError("%s cannot appear twice in this molecule" % obj)
        elif obj.molecule is not None:
            raise ValueError("%s is already a member of %s" % (obj, obj.molecule))

    def append(self, obj):
        """ Adds obj to this molecule. Equivalent to ``obj.molecule = mol``

        Args:
            obj (object): object to add

        Note:
            It's much more efficient to use the ``extend`` method for lists of objects

        Raises:
            ValueError: If obj is already part of a different molecule, or is part of
               a larger substructure (such as a chain or residue)
        """
        self._error_if_object_owned(obj)
        super(MolecularBaseList, self).append(obj)

    def extend(self, objs):
        """ Adds a list of objects to this molecule. More efficient than adding them individually.

        If the object is already assigned to a residue, the residue will be assigned to this molecule
        as well.

        Args:
            obj (List[object]): objects to add

        Raises:
            ValueError: If obj is already part of a different molecule
        """
        for o in objs:
            self._error_if_object_owned(o)
        super(MolecularBaseList, self).extend(objs)

    def insert(self, index, obj):
        self._error_if_object_owned(obj)
        super(MolecularBaseList, self).insert(index, obj)
    insert.__doc__ = append.__doc__

    def remove(self, obj):
        """ Removes obj from this molecule. Equivalent to running ``obj.molecule = None``

        The obj is automatically removed from its residue as well.

        Args:
            obj (object): object to remove

        Raises:
            ValueError: If obj is not part of the molecule
        """
        assert obj is self[obj.index]
        self.pop(obj.index)

    def pop(self, index=-1):
        return super(MolecularBaseList, self).pop(index)
    pop.__doc__ = remove.__doc__


class MolecularAtomList(MolecularBaseList, AtomListOperationMixin):
    """ The master list of atoms in a molecule.
    """
    def _error_if_obj_owned(self, atom):
        if atom.residue is not None and atom.residue.molecule is not self._mol:
            raise ValueError("Cannot individually assign %s to %s, because it is part of %s" %
                             (atom, self._mol, atom.residue))
        super(MolecularAtomList, self)._error_if_object_owned(atom)

    def _ownedinsert(self, index, atom):
        """ Called by residues/chains to insert atoms/residues into the middle of the list

        Not public - requires that the atoms be part of residues/chains already owned by the
        molecule.
        """
        self.insert(index, atom)
        assert atom.molecule is self._mol

    @utils.doc_inherit
    def append(self, atom):
        self.extend([atom])

    def extend(self, atoms):
        """
        Note:
            Internally, this is THE place where new atoms are added to a molecular structure
        """
        self._error_if_cant_add_atoms(atoms)
        super(MolecularAtomList, self).extend(atoms)

        # assign default residues and chains where necessary
        for atom in atoms:
            if atom.residue is None:
                self._mol._defresidue.add(atom)

            if atom.residue.chain is None:
                self._mol._defchain.add(atom.residue)

            # this part sets up all primary structure
            if atom.chain.molecule is not self._mol:
                assert atom.chain.molecule is None
                self._mol.chains.add(atom.chain)

        # Resize the physics arrays
        self._mol.ndims = 3 * len(self)
        self._mol.masses = u.array([atom.mass for atom in self]).defunits()
        self._mol.dim_masses = u.broadcast_to(self.masses, (3, len(self))).T
        self._mol._dof = None
        self._mol._positions = u.array([atom.position for atom in self])
        self._mol._momenta = u.array([atom.momentum for atom in self])

        # Mark the atoms as owned
        for atom in atoms:
            atom._position = atom._momentum = None
            atom._molecule = self._mol

    def _error_if_cant_add_atoms(self, atoms):
        atoms_to_add = set(atoms)
        structure_to_add = set()
        atoms_in_structure = set()
        for atom in atoms:
            for obj in (atom.residue, atom.chain):
                if obj is not None and obj not in structure_to_add:
                    structure_to_add.add(obj)
                    atoms_in_structure.update(obj.atoms)

        if atoms_in_structure > atoms_to_add:
            raise ValueError("Can't add atoms - they're part of a larger structure")

    @utils.doc_inherit
    def pop(self, index=-1):
        atom = super(MolecularAtomList, self).pop(index)
        atom._molecule = None
        atom.residue = None
        atom.chain = None
        return atom


class MolecularResidueList(MolecularBaseList):
    """ The master list of residues in a molecule.
    """
    def _error_if_obj_owned(self, res):
        if res.chain is not None and res.molecule is not self._mol:
            raise ValueError("Cannot individually assign %s to %s, because it is part of %s" %
                             (res, self._mol, res.residue))
        super(MolecularResidueList, self)._error_if_object_owned(res)

    @utils.doc_inherit
    def append(self, res):
        self.extend([res])

    def pop(self, index=-1):
        res = super(MolecularResidueList, self).pop(index)
        res._molecule = None
        res.residue = None
        res.chain = None
        return res

    def extend(self, residues):
        atoms = []
        for r in residues:
            atoms.extend(r.atoms)
        self._mol.atoms.extend(atoms)


class MolecularChainList(MolecularBaseList, Instance):

    @utils.kwargs_from(Instance)
    def __init__(self, mol, **kwargs):
        self._mol = mol
        Instance.__init__(self, **kwargs)


class BondGraph(object):
    pass



def wutwut():
    # symmetrize bonds between the new atoms and the pre-existing molecule
    bonds = self._build_bonds(self.atoms)
    for newatom in newatoms:
        for nbr in bonds[newatom]:
            if nbr in self.bond_graph:  # i.e., it's part of the original molecule
                bonds[nbr][newatom] = bonds[newatom][nbr]

