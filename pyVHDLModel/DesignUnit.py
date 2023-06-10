# ==================================================================================================================== #
#             __     ___   _ ____  _     __  __           _      _                                                     #
#   _ __  _   \ \   / / | | |  _ \| |   |  \/  | ___   __| | ___| |                                                    #
#  | '_ \| | | \ \ / /| |_| | | | | |   | |\/| |/ _ \ / _` |/ _ \ |                                                    #
#  | |_) | |_| |\ V / |  _  | |_| | |___| |  | | (_) | (_| |  __/ |                                                    #
#  | .__/ \__, | \_/  |_| |_|____/|_____|_|  |_|\___/ \__,_|\___|_|                                                    #
#  |_|    |___/                                                                                                        #
# ==================================================================================================================== #
# Authors:                                                                                                             #
#   Patrick Lehmann                                                                                                    #
#                                                                                                                      #
# License:                                                                                                             #
# ==================================================================================================================== #
# Copyright 2017-2023 Patrick Lehmann - Boetzingen, Germany                                                            #
# Copyright 2016-2017 Patrick Lehmann - Dresden, Germany                                                               #
#                                                                                                                      #
# Licensed under the Apache License, Version 2.0 (the "License");                                                      #
# you may not use this file except in compliance with the License.                                                     #
# You may obtain a copy of the License at                                                                              #
#                                                                                                                      #
#   http://www.apache.org/licenses/LICENSE-2.0                                                                         #
#                                                                                                                      #
# Unless required by applicable law or agreed to in writing, software                                                  #
# distributed under the License is distributed on an "AS IS" BASIS,                                                    #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.                                             #
# See the License for the specific language governing permissions and                                                  #
# limitations under the License.                                                                                       #
#                                                                                                                      #
# SPDX-License-Identifier: Apache-2.0                                                                                  #
# ==================================================================================================================== #
#
"""
This module contains parts of an abstract document language model for VHDL.

Design units are contexts, entities, architectures, packages and their bodies as well as configurations.
"""
from typing import List, Dict, Union, Iterable, Optional as Nullable

from pyTooling.Decorators import export
from pyTooling.Graph import Vertex

from pyVHDLModel.Exception  import VHDLModelException
from pyVHDLModel.Base       import ModelEntity, NamedEntityMixin, DocumentedEntityMixin
from pyVHDLModel.Namespace  import Namespace
from pyVHDLModel.Regions    import ConcurrentDeclarationRegionMixin
from pyVHDLModel.Symbol     import Symbol, PackageSymbol, EntitySymbol, LibraryReferenceSymbol
from pyVHDLModel.Interface  import GenericInterfaceItem, PortInterfaceItem
from pyVHDLModel.Object     import DeferredConstant
from pyVHDLModel.Concurrent import ConcurrentStatement, ConcurrentStatementsMixin


@export
class Reference(ModelEntity):
	"""
	A base-class for all references.

	.. seealso::

	   * :class:`~pyVHDLModel.DesignUnit.LibraryClause`
	   * :class:`~pyVHDLModel.DesignUnit.UseClause`
	   * :class:`~pyVHDLModel.DesignUnit.ContextReference`
	"""

	_symbols:       List[Symbol]

	def __init__(self, symbols: Iterable[Symbol]):
		super().__init__()

		self._symbols = [s for s in symbols]

	@property
	def Symbols(self) -> List[Symbol]:
		return self._symbols


@export
class LibraryClause(Reference):
	"""
	Represents a library clause.

	.. admonition:: Example

	    .. code-block:: VHDL

	       library ieee;
	"""

	@property
	def Symbols(self) -> List[LibraryReferenceSymbol]:
		return self._symbols


@export
class UseClause(Reference):
	"""
	Represents a use clause.

	.. admonition:: Example

	    .. code-block:: VHDL

	       use ieee.numeric_std.all;
	"""


@export
class ContextReference(Reference):
	# TODO: rename to ContextClause?
	"""
	Represents a context reference.

	.. hint:: It's called *context reference* not *context clause* by the LRM.

	.. admonition:: Example

	    .. code-block:: VHDL

	       context ieee.ieee_std_context;
	"""


ContextUnion = Union[
	LibraryClause,
	UseClause,
	ContextReference
]


@export
class DesignUnitWithContextMixin:  # (metaclass=ExtendedType, useSlots=True):
	pass


@export
class DesignUnit(ModelEntity, NamedEntityMixin, DocumentedEntityMixin):
	"""
	A base-class for all design units.

	.. seealso::

	   * :class:`Primary design units <pyVHDLModel.DesignUnit.PrimaryUnit>`

	     * :class:`~pyVHDLModel.DesignUnit.Context`
	     * :class:`~pyVHDLModel.DesignUnit.Entity`
	     * :class:`~pyVHDLModel.DesignUnit.Package`
	     * :class:`~pyVHDLModel.DesignUnit.Configuration`

	   * :class:`Secondary design units <pyVHDLModel.DesignUnit.SecondaryUnit>`

	     * :class:`~pyVHDLModel.DesignUnit.Architecture`
	     * :class:`~pyVHDLModel.DesignUnit.PackageBody`
	"""

	_library:             'Library'                        #: The VHDL library, the design unit was analyzed into.

	# Either written as statements before (e.g. entity, architecture, package, ...), or as statements inside (context)
	_contextItems:        List['ContextUnion']             #: List of all context items (library, use and context clauses).
	_libraryReferences:   List['LibraryClause']            #: List of library clauses.
	_packageReferences:   List['UseClause']                #: List of use clauses.
	_contextReferences:   List['ContextReference']         #: List of context clauses.

	_referencedLibraries: Dict[str, 'Library']             #: Referenced libraries based on explicit library clauses or implicit inheritance
	_referencedPackages:  Dict[str, Dict[str, 'Package']]  #: Referenced packages based on explicit use clauses or implicit inheritance
	_referencedContexts:  Dict[str, 'Context']             #: Referenced contexts based on explicit context references or implicit inheritance

	_dependencyVertex:    Vertex[None, None, str, 'DesignUnit', None, None, None, None, None, None, None, None, None, None, None, None, None]  #: The vertex in the dependency graph
	_hierarchyVertex:     Vertex[None, None, str, 'DesignUnit', None, None, None, None, None, None, None, None, None, None, None, None, None]  #: The vertex in the hierarchy graph

	_namespace:           'Namespace'

	def __init__(self, identifier: str, contextItems: Iterable[ContextUnion] = None, documentation: str = None):
		"""
		Initializes a design unit.

		:param identifier:    Identifier (name) of the design unit.
		:param contextItems:  A sequence of library, use or context clauses.
		:param documentation: Associated documentation of the design unit.
		"""
		super().__init__()
		NamedEntityMixin.__init__(self, identifier)
		DocumentedEntityMixin.__init__(self, documentation)

		self._library = None

		self._contextItems = []
		self._libraryReferences = []
		self._packageReferences = []
		self._contextReferences = []

		if contextItems is not None:
			for item in contextItems:
				self._contextItems.append(item)
				if isinstance(item, UseClause):
					self._packageReferences.append(item)
				elif isinstance(item, LibraryClause):
					self._libraryReferences.append(item)
				elif isinstance(item, ContextReference):
					self._contextReferences.append(item)

		self._referencedLibraries = {}
		self._referencedPackages = {}
		self._referencedContexts = {}

		self._dependencyVertex = None
		self._hierarchyVertex = None

		self._namespace = Namespace(self._normalizedIdentifier)

	@property
	def Document(self) -> 'Document':
		return self._parent

	@Document.setter
	def Document(self, document: 'Document') -> None:
		self._parent = document

	@property
	def Library(self) -> 'Library':
		return self._library

	@Library.setter
	def Library(self, library: 'Library') -> None:
		self._library = library

	@property
	def ContextItems(self) -> List['ContextUnion']:
		"""
		Read-only property to access the sequence of all context items comprising library, use and context clauses
		(:attr:`_contextItems`).

		:returns: Sequence of context items.
		"""
		return self._contextItems

	@property
	def ContextReferences(self) -> List['ContextReference']:
		"""
		Read-only property to access the sequence of context clauses (:attr:`_contextReferences`).

		:returns: Sequence of context clauses.
		"""
		return self._contextReferences

	@property
	def LibraryReferences(self) -> List['LibraryClause']:
		"""
		Read-only property to access the sequence of library clauses (:attr:`_libraryReferences`).

		:returns: Sequence of library clauses.
		"""
		return self._libraryReferences

	@property
	def PackageReferences(self) -> List['UseClause']:
		"""
		Read-only property to access the sequence of use clauses (:attr:`_packageReferences`).

		:returns: Sequence of use clauses.
		"""
		return self._packageReferences

	@property
	def ReferencedLibraries(self) -> Dict[str, 'Library']:
		return self._referencedLibraries

	@property
	def ReferencedPackages(self) -> Dict[str, 'Package']:
		return self._referencedPackages

	@property
	def ReferencedContexts(self) -> Dict[str, 'Context']:
		return self._referencedContexts

	@property
	def DependencyVertex(self) -> Vertex:
		return self._dependencyVertex

	@property
	def HierarchyVertex(self) -> Vertex:
		return self._hierarchyVertex


@export
class PrimaryUnit(DesignUnit):
	"""
	A base-class for all primary design units.

	.. seealso::

	   * :class:`~pyVHDLModel.DesignUnit.Context`
	   * :class:`~pyVHDLModel.DesignUnit.Entity`
	   * :class:`~pyVHDLModel.DesignUnit.Package`
	   * :class:`~pyVHDLModel.DesignUnit.Configuration`
	"""


@export
class SecondaryUnit(DesignUnit):
	"""
	A base-class for all secondary design units.

	.. seealso::

	   * :class:`~pyVHDLModel.DesignUnit.Architecture`
	   * :class:`~pyVHDLModel.DesignUnit.PackageBody`
	"""


@export
class Context(PrimaryUnit):
	"""
	Represents a context declaration.

	A context contains a generic list of all its items (library clauses, use clauses and context references) in
	:data:`_references`.

	Furthermore, when a context gets initialized, the item kinds get separated into individual lists:

	* :class:`~pyVHDLModel.DesignUnit.LibraryClause` |rarr| :data:`_libraryReferences`
	* :class:`~pyVHDLModel.DesignUnit.UseClause` |rarr| :data:`_packageReferences`
	* :class:`~pyVHDLModel.DesignUnit.ContextReference` |rarr| :data:`_contextReferences`

	When :meth:`pyVHDLModel.Design.LinkContexts` got called, these lists were processed and the fields:

	* :data:`_referencedLibraries` (:pycode:`Dict[libName, Library]`)
	* :data:`_referencedPackages` (:pycode:`Dict[libName, [pkgName, Package]]`)
	* :data:`_referencedContexts` (:pycode:`Dict[libName, [ctxName, Context]]`)

	are populated.

	.. admonition:: Example

	    .. code-block:: VHDL

	       context ctx is
	         -- ...
	       end context;
	"""

	_references:        List[ContextUnion]
	_libraryReferences: List[LibraryClause]
	_packageReferences: List[UseClause]
	_contextReferences: List[ContextReference]

	def __init__(self, identifier: str, references: Iterable[ContextUnion] = None, documentation: str = None):
		super().__init__(identifier, None, documentation)

		self._references = []
		self._libraryReferences = []
		self._packageReferences = []
		self._contextReferences = []

		if references is not None:
			for reference in references:
				self._references.append(reference)
				reference._parent = self

				if isinstance(reference, LibraryClause):
					self._libraryReferences.append(reference)
				elif isinstance(reference, UseClause):
					self._packageReferences.append(reference)
				elif isinstance(reference, ContextReference):
					self._contextReferences.append(reference)
				else:
					raise VHDLModelException()  # FIXME: needs exception message

	@property
	def LibraryReferences(self) -> List[LibraryClause]:
		return self._libraryReferences

	@property
	def PackageReferences(self) -> List[UseClause]:
		return self._packageReferences

	@property
	def ContextReferences(self) -> List[ContextReference]:
		return self._contextReferences

	def __str__(self):
		lib = self._library.Identifier + "?" if self._library is not None else ""

		return f"Context: {lib}.{self._identifier}"


@export
class Package(PrimaryUnit, DesignUnitWithContextMixin, ConcurrentDeclarationRegionMixin):
	"""
	Represents a package declaration.

	.. admonition:: Example

	    .. code-block:: VHDL

	       package pkg is
	         -- ...
	       end package;
	"""

	_genericItems:      List[GenericInterfaceItem]
	_declaredItems:     List

	_deferredConstants: Dict[str, DeferredConstant]
	_components:        Dict[str, 'Component']

	def __init__(self, identifier: str, contextItems: Iterable[ContextUnion] = None, genericItems: Iterable[GenericInterfaceItem] = None, declaredItems: Iterable = None, documentation: str = None):
		super().__init__(identifier, contextItems, documentation)
		DesignUnitWithContextMixin.__init__(self)
		ConcurrentDeclarationRegionMixin.__init__(self, declaredItems)

		# TODO: extract to mixin
		self._genericItems = []  # TODO: convert to dict
		if genericItems is not None:
			for generic in genericItems:
				self._genericItems.append(generic)
				generic._parent = self

		self._deferredConstants = {}
		self._components = {}

	@property
	def GenericItems(self) -> List[GenericInterfaceItem]:
		return self._genericItems

	@property
	def DeclaredItems(self) -> List:
		return self._declaredItems

	@property
	def DeferredConstants(self):
		return self._deferredConstants

	@property
	def Components(self):
		return self._components

	def _IndexOtherDeclaredItem(self, item):
		if isinstance(item, DeferredConstant):
			for normalizedIdentifier in item.NormalizedIdentifiers:
				self._deferredConstants[normalizedIdentifier] = item
		elif isinstance(item, Component):
			self._components[item.NormalizedIdentifier] = item
		else:
			super()._IndexOtherDeclaredItem(item)

	def __str__(self) -> str:
		lib = self._library.Identifier if self._library is not None else "%"

		return f"Package: '{lib}.{self._identifier}'"

	def __repr__(self) -> str:
		lib = self._library.Identifier if self._library is not None else "%"

		return f"{lib}.{self._identifier}"


@export
class PackageBody(SecondaryUnit, DesignUnitWithContextMixin, ConcurrentDeclarationRegionMixin):
	"""
	Represents a package body declaration.

	.. admonition:: Example

	    .. code-block:: VHDL

	       package body pkg is
	         -- ...
	       end package body;
	"""

	_package:       PackageSymbol
	_declaredItems: List

	def __init__(self, packageSymbol: PackageSymbol, contextItems: Iterable[ContextUnion] = None, declaredItems: Iterable = None, documentation: str = None):
		super().__init__(packageSymbol.Name.Identifier, contextItems, documentation)
		DesignUnitWithContextMixin.__init__(self)
		ConcurrentDeclarationRegionMixin.__init__(self, declaredItems)

		self._package = packageSymbol
		packageSymbol._parent = self

	@property
	def Package(self) -> PackageSymbol:
		return self._package

	@property
	def DeclaredItems(self) -> List:
		return self._declaredItems

	def LinkDeclaredItemsToPackage(self):
		pass

	def __str__(self) -> str:
		lib = self._library._identifier + "?" if self._library is not None else ""

		return f"Package Body: {lib}.{self._identifier}(body)"

	def __repr__(self) -> str:
		lib = self._library._identifier + "?" if self._library is not None else ""

		return f"{lib}.{self._identifier}(body)"


@export
class Entity(PrimaryUnit, DesignUnitWithContextMixin, ConcurrentDeclarationRegionMixin, ConcurrentStatementsMixin):
	"""
	Represents an entity declaration.

	.. admonition:: Example

	    .. code-block:: VHDL

	       entity ent is
	         -- ...
	       end entity;
	"""

	_genericItems:  List[GenericInterfaceItem]
	_portItems:     List[PortInterfaceItem]

	_architectures: Dict[str, 'Architecture']

	def __init__(
		self,
		identifier: str,
		contextItems: Iterable[ContextUnion] = None,
		genericItems: Iterable[GenericInterfaceItem] = None,
		portItems: Iterable[PortInterfaceItem] = None,
		declaredItems: Iterable = None,
		statements: Iterable[ConcurrentStatement] = None,
		documentation: str = None
	):
		super().__init__(identifier, contextItems, documentation)
		DesignUnitWithContextMixin.__init__(self)
		ConcurrentDeclarationRegionMixin.__init__(self, declaredItems)
		ConcurrentStatementsMixin.__init__(self, statements)

		# TODO: extract to mixin
		self._genericItems = []
		if genericItems is not None:
			for item in genericItems:
				self._genericItems.append(item)
				item._parent = self

		# TODO: extract to mixin
		self._portItems = []
		if portItems is not None:
			for item in portItems:
				self._portItems.append(item)
				item._parent = self

		self._architectures = {}

	# TODO: extract to mixin for generics
	@property
	def GenericItems(self) -> List[GenericInterfaceItem]:
		return self._genericItems

	# TODO: extract to mixin for ports
	@property
	def PortItems(self) -> List[PortInterfaceItem]:
		return self._portItems

	@property
	def Architectures(self) -> Dict[str, 'Architecture']:
		return self._architectures

	def __str__(self) -> str:
		lib = self._library._identifier if self._library is not None else "%"
		archs = ', '.join(self._architectures.keys()) if self._architectures else "%"

		return f"Entity: '{lib}.{self._identifier}({archs})'"

	def __repr__(self) -> str:
		lib = self._library._identifier if self._library is not None else "%"
		archs = ', '.join(self._architectures.keys()) if self._architectures else "%"

		return f"{lib}.{self._identifier}({archs})"


@export
class Architecture(SecondaryUnit, DesignUnitWithContextMixin, ConcurrentDeclarationRegionMixin, ConcurrentStatementsMixin):
	"""
	Represents an architecture declaration.

	.. admonition:: Example

	    .. code-block:: VHDL

	       architecture rtl of ent is
	         -- ...
	       begin
	         -- ...
	       end architecture;
	"""

	_library:       'Library' = None
	_entity: EntitySymbol

	def __init__(self, identifier: str, entity: EntitySymbol, contextItems: Iterable[Context] = None, declaredItems: Iterable = None, statements: Iterable['ConcurrentStatement'] = None, documentation: str = None):
		super().__init__(identifier, contextItems, documentation)
		DesignUnitWithContextMixin.__init__(self)
		ConcurrentDeclarationRegionMixin.__init__(self, declaredItems)
		ConcurrentStatementsMixin.__init__(self, statements)

		self._entity = entity
		entity._parent = self

	@property
	def Entity(self) -> EntitySymbol:
		return self._entity

	# TODO: move to Design Unit
	@property
	def Library(self) -> 'Library':
		return self._library

	@Library.setter
	def Library(self, library: 'Library') -> None:
		self._library = library

	def __str__(self) -> str:
		lib = self._library._identifier if self._library is not None else "%"
		ent = self._entity._identifier if self._entity is not None else "%"

		return f"Architecture: {lib}.{ent}({self._identifier})"

	def __repr__(self) -> str:
		lib = self._library._identifier if self._library is not None else "%"
		ent = self._entity.Name._identifier if self._entity is not None else "%"

		return f"{lib}.{ent}({self._identifier})"


@export
class Component(ModelEntity, NamedEntityMixin, DocumentedEntityMixin):
	"""
	Represents a configuration declaration.

	.. admonition:: Example

	    .. code-block:: VHDL

	       component ent is
	         -- ...
	       end component;
	"""

	_genericItems:      List[GenericInterfaceItem]
	_portItems:         List[PortInterfaceItem]

	_entity:            Nullable[Entity]

	def __init__(self, identifier: str, genericItems: Iterable[GenericInterfaceItem] = None, portItems: Iterable[PortInterfaceItem] = None, documentation: str = None):
		super().__init__()
		NamedEntityMixin.__init__(self, identifier)
		DocumentedEntityMixin.__init__(self, documentation)

		# TODO: extract to mixin
		self._genericItems = []
		if genericItems is not None:
			for item in genericItems:
				self._genericItems.append(item)
				item._parent = self

		# TODO: extract to mixin
		self._portItems = []
		if portItems is not None:
			for item in portItems:
				self._portItems.append(item)
				item._parent = self

	@property
	def GenericItems(self) -> List[GenericInterfaceItem]:
		return self._genericItems

	@property
	def PortItems(self) -> List[PortInterfaceItem]:
		return self._portItems

	@property
	def Entity(self) -> Nullable[Entity]:
		return self._entity

	@Entity.setter
	def Entity(self, value: Entity) -> None:
		self._entity = value


@export
class Configuration(PrimaryUnit, DesignUnitWithContextMixin):
	"""
	Represents a configuration declaration.

	.. admonition:: Example

	    .. code-block:: VHDL

	       configuration cfg of ent is
	         for rtl
	           -- ...
	         end for;
	       end configuration;
	"""

	def __init__(self, identifier: str, contextItems: Iterable[Context] = None, documentation: str = None):
		super().__init__(identifier, contextItems, documentation)
		DesignUnitWithContextMixin.__init__(self)

	def __str__(self) -> str:
		lib = self._library._identifier if self._library is not None else "%"

		return f"Configuration: {lib}.{self._identifier}"

	def __repr__(self) -> str:
		lib = self._library._identifier if self._library is not None else "%"

		return f"{lib}.{self._identifier}"
