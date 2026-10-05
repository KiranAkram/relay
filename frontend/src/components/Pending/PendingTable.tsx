import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/** Loading skeleton for any list page. */
const PendingTable = ({ columns = 4, rows = 5 }) => (
  <Table>
    <TableHeader>
      <TableRow>
        {Array.from({ length: columns }).map((_, index) => (
          <TableHead key={index}>
            <Skeleton className="h-4 w-24" />
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
    <TableBody>
      {Array.from({ length: rows }).map((_, row) => (
        <TableRow key={row}>
          {Array.from({ length: columns }).map((_, index) => (
            <TableCell key={index}>
              <Skeleton className="h-4 w-full" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </TableBody>
  </Table>
)

export default PendingTable
