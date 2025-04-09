import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class CountRectangles{
  public static Integer countRectangles(int radius){
    int count = 0;
    int i = 0;
    while (i < radius * radius * radius){
      count++;
      i++;
    }
    return count;
  }
}

class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        int arg00 = 2;
        int x0 = CountRectangles.countRectangles(2);
        int v0 = 8;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 1;
        int x1 = CountRectangles.countRectangles(1);
        int v1 = 1;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 0;
        int x2 = CountRectangles.countRectangles(0);
        int v2 = 0;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
