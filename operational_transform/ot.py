from typing import Tuple

class Operation:
    """
    Represents a single editing operation on a shared text document.
    Attributes:
        op_type: "insert" or "delete"
        position: Index in the text where the operation is applied
        text: The inserted string (for insert ops)
        length: Number of chars to delete (for delete ops)
        base_version: The document version the client thought it was editing
    """

    def __init__(self, op_type :str, position: int, text: str, length: int=0, base_version: int=0, op_id=None):
        self.op_type = op_type
        self.position = position
        self.text = text
        self.length = length
        self.base_version = base_version
        self.op_id = op_id 

    def __repr__(self):
        if self.op_type == 'insert':
            return f"Operation(insert, pos={self.position}, text='{self.text}', base_ver={self.base_version})"
        elif self.op_type == 'delete':
            return f"Operation(delete, pos={self.position}, length={self.length}, base_ver={self.base_version})"
        else:
            return f"Operation(unknown, base_ver={self.base_version})"
        
def transform(opA: Operation, opB: Operation) -> Tuple[Operation, Operation]:
    """
    Transforms opA and opB so that applying them in either order yields the same final result.
    Returns the transformed pair (A', B').
    """

    #Copy so that it doens't mutate the original
    A = Operation(opA.op_type, opA.position, opA.text, opA.length, opA.base_version)
    B = Operation(opB.op_type, opB.position, opB.text, opB.length, opB.base_version)

    """
    Transforms generally have 4 cases that needed to be accounted for:
    1. Insert v Insert
    2. Insert v Delete
    3. Delete v Insert
    4. Delete v Delete
    """

    if A.op_type == 'insert' and B.op_type == 'insert':
        if A.position < B.position:
            B.position += len(A.text)
        elif A.position > B.position:
            A.position += len(B.text)
        else:
            #in the case that position values are equal
            B.position += len(A.text)
    elif A.op_type == 'insert' and B.op_type == 'delete':
        if A.position <= B.position:
            B.position += len(A.text)
        else:
            #need to shift A position in case it gets deleted as well
            shift = min(A.position - B.position, B.length)
            A.position -= shift
    elif A.op_type == 'delete' and B.op_type == 'insert':
        #basically the same, just need to flip and reuse
        Bprime, Aprime = transform(B, A)
        return (Aprime, Bprime)
    elif A.op_type == 'delete' and B.op_type == 'delete':
        if A.position < B.position:
            overlap = (A.position + A.length) - B.position
            if overlap > 0:
                B.position = A.position
                B.length += overlap
            else:
                pass
        else:
            overlap = (B.position + B.length) - A.position
            if overlap > 0:
                A.position = B.position
                A.length += overlap
            else:
                pass
    return (A,B)

class DocumentModel:
    """
    Holds the shared text document and a version number that increments after each applied operation.
    """
    def __init__(self, initial_text: str = ""):
        self.text = initial_text
        self.version = 0

    def apply_operation(self, op: Operation):
        """
        Applies the operation to the document and increments the version.
        """
        if op.op_type == 'insert':
            self.text = self.text[:op.position] + op.text + self.text[op.position:]
        elif op.op_type == 'delete':
            self.text = self.text[:op.position] + self.text[op.position + op.length:]
        else:
            raise ValueError("Unknown operation type.")

        self.version += 1

class OTServer:
    """
    Manages the canonical DocumentModel and operation history for concurrency resolution.
    """
    def __init__(self):
        self.document = DocumentModel("Hello OT!")  # or load from DB if desired
        self.history = []  # List of all operations applied to the doc (for versioning)

    async def handle_incoming_operation(self, op: Operation, sio, room=None):
        unseen_ops = self.history[op.base_version:]
        for old_op in unseen_ops:
            op, _ = transform(op, old_op)

        self.document.apply_operation(op)
        self.history.append(op)

        # Broadcast the op back, INCLUDING op.op_id
        update_payload = {
            "opId": op.op_id,
            "op_type": op.op_type,
            "position": op.position,
            "text": op.text,
            "length": op.length,
            "new_version": self.document.version
        }
        await sio.emit('ot_update', update_payload, room=room)


    def get_document_state(self):
        return {
            "text": self.document.text,
            "version": self.document.version
        }